# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 OpenCraft
# License: AGPLv3
"""
This module contains a mixin that allows third aprty XBlocks to be easily edited within edX
Studio just like the built-in modules. No configuration required, just add
StudioEditableXBlockMixin to your XBlock.
"""

# Imports ###########################################################

import json
import logging

from xblock.core import XBlock
from xblock.fields import Scope, JSONField, Integer, Float, Boolean, String
from xblock.exceptions import JsonHandlerError
from xblock.fragment import Fragment
from xblock.validation import Validation

from xblockutils.resources import ResourceLoader

# Globals ###########################################################

log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)

class FutureFields(object):
    """
    A helper class whose attribute values come from the specified dictionary or fallback object.
    """
    def __init__(self, new_fields_dict, newly_removed_fields, fallback_obj):
        self._new_fields_dict = new_fields_dict
        self._blacklist = newly_removed_fields
        self._fallback_obj = fallback_obj
    def __getattr__(self, name):
        try:
            return self._new_fields_dict[name]
        except KeyError:
            if name in self._blacklist:
                # Pretend like this field is not actually set, since we're going to be resetting it to default
                return self._fallback_obj.fields[name].default
            return getattr(self._fallback_obj, name)


class StudioEditableXBlockMixin(object):
    """
    An XBlock mixin to provide convenient use of an XBlock in Studio.
    """
    editable_fields = ()  # Set this to a list of the names of fields to appear in the editor


    def studio_view(self, context):
        """
        Render a form for editing this XBlock
        """
        fragment = Fragment()
        context = {'fields': []}
        # Build a list of all the fields that can be edited:
        for field_name in self.editable_fields:
            field = self.fields[field_name]
            assert field.scope in (Scope.content, Scope.settings)
            field_info = self._make_field_info(field_name, field)
            if field_info is not None:
                context["fields"].append(field_info)
        fragment.content = loader.render_template('templates/studio_edit.html', context)
        fragment.add_javascript(loader.load_unicode('public/js/src/studio_edit.js'))
        # Function StudioEditableXBlockMixin will be called from subclass client side JavaScript
        # fragment.initialize_js('StudioEditableXBlockMixin')
        return fragment

    def _make_field_info(self, field_name, field):
        """
        Create the information that the template needs to render a form field for this field.
        """
        supported_field_types = (
            (Integer, 'integer'),
            (Float, 'float'),
            (Boolean, 'boolean'),
            (String, 'string'),
            (JSONField, 'generic'),  # This is last so as a last resort we display a text field w/ the JSON string
        )
        info = {
            'name': field_name,
            'display_name': field.display_name,
            'is_set': field.is_set_on(self),
            'default': field.default,
            'value': field.read_from(self),
            'has_values': False,
            'help': field.help,
            'allow_reset': field.runtime_options.get('resettable_editor', True),
        }
        for type_class, type_name in supported_field_types:
            if isinstance(field, type_class):
                info['type'] = type_name
                # If String fields are declared like String(..., multiline_editor=True), then call them "text" type:
                editor_type = field.runtime_options.get('multiline_editor')
                if type_class is String and editor_type:
                    if editor_type == "html":
                        info['type'] = 'html'
                    else:
                        info['type'] = 'text'
                break
        if "type" not in info:
            return None  # This is not a field we can support (it doesn't even have a JSON representation)
        if info["type"] == "generic":
            # Convert value to JSON string if we're treating this field generically:
            info["value"] = json.dumps(info["value"])
            info["default"] = json.dumps(info["default"])

        if field.values and not isinstance(field, Boolean):
            info['has_values'] = True
            # This field has only a limited number of pre-defined options.
            # Protip: when defining the field, values= can be a callable.
            if isinstance(field.values, dict) and isinstance(field, (Float, Integer)):
                # e.g. {"min": 0 , "max": 10, "step": .1}
                info["min"] = field.values["min"]
                info["max"] = field.values["max"]
                info["step"] = field.values["step"]
            else:
                # e.g. [1, 2, 3] or [ {"display_name": "Always", "value": "always"}, {...}, ... ]
                values = field.values
                if "display_name" not in values[0]:
                    values = [{"display_name": val, "value": val} for val in values]
                info['values'] = values
        return info

    @XBlock.json_handler
    def submit_studio_edits(self, data, suffix=''):
        """
        AJAX handler for studio_view() Save button
        """
        values = {}  # dict of new field values we are updating
        to_reset = []  # list of field names to delete from this XBlock
        for field_name in self.editable_fields:
            field = self.fields[field_name]
            if field_name in data['values']:
                if isinstance(field, JSONField):
                    values[field_name] = field.from_json(data['values'][field_name])
                else:
                    raise JsonHandlerError(400, "Unsupported field type: {}".format(field_name))
            elif field_name in data['defaults'] and field.is_set_on(self):
                to_reset.append(field_name)
        self.clean_studio_edits(values)
        validation = Validation(self.scope_ids.usage_id)
        # We cannot set the fields on self yet, because even if validation fails, studio is going to save any changes we
        # make. So we create a "fake" object that has all the field values we are about to set.
        preview_data = FutureFields(
            new_fields_dict=values,
            newly_removed_fields=to_reset,
            fallback_obj=self
        )
        self.validate_field_data(validation, preview_data)
        if validation:
            for field_name, value in values.iteritems():
                setattr(self, field_name, value)
            for field_name in to_reset:
                self.fields[field_name].delete_from(self)
            return {'result': 'success', 
                    'values': values, 
                    'to_reset':to_reset}
        else:
            raise JsonHandlerError(400, validation.to_json())

    def clean_studio_edits(self, data):
        """
        Given POST data dictionary 'data', clean the data before validating it.
        e.g. fix capitalization, remove trailing spaces, etc.
        """
        # Example:
        # if "name" in data:
        #     data["name"] = data["name"].strip()
        pass

    def validate_field_data(self, validation, data):
        """
        Validate this block's field data. Instead of checking fields like self.name, check the
        fields set on data, e.g. data.name. This allows the same validation method to be re-used
        for the studio editor. Any errors found should be added to "validation".

        This method should not return any value or raise any exceptions.
        All of this XBlock's fields should be found in "data", even if they aren't being changed
        or aren't even set (i.e. are defaults).
        """
        # Example:
        # if data.count <=0:
        #     validation.add(ValidationMessage(ValidationMessage.ERROR, u"Invalid count"))
        pass

    def validate(self):
        """
        Validates the state of this XBlock.

        Subclasses should override validate_field_data() to validate fields and override this
        only for validation not related to this block's field values.
        """
        validation = super(StudioEditableXBlockMixin, self).validate()
        self.validate_field_data(validation, self)
        return validation


class StudioContainerXBlockMixin(object):
    """
    An XBlock mixin to provide convenient use of an XBlock in Studio
    that wants to allow the user to assign children to it.
    """
    has_author_view = True  # Without this flag, studio will use student_view on newly-added blocks :/

    def render_children(self, context, fragment, can_reorder=True, can_add=False):
        """
        Renders the children of the module with HTML appropriate for Studio. If can_reorder is
        True, then the children will be rendered to support drag and drop.
        """
        contents = []

        for child_id in self.children:
            child = self.runtime.get_block(child_id)
            if can_reorder:
                context['reorderable_items'].add(child.scope_ids.usage_id)
            rendered_child = child.render('author_view' if hasattr(child, 'author_view') else 'student_view', context)
            fragment.add_frag_resources(rendered_child)

            contents.append({
                'id': child.location.to_deprecated_string(),
                'content': rendered_child.content
            })

        fragment.add_content(self.runtime.render_template("studio_render_children_view.html", {
            'items': contents,
            'xblock_context': context,
            'can_add': can_add,
            'can_reorder': can_reorder,
        }))

    def author_view(self, context):
        """
        Display a the studio editor when the user has clicked "View" to see the container view,
        otherwise just show the normal 'author_preview_view' or 'student_view' preview.
        """
        root_xblock = context.get('root_xblock')
        is_root = root_xblock and root_xblock.location == self.location

        if is_root:
            # User has clicked the "View" link. Show an editable preview of this block's children
            return self.author_edit_view(context)
        else:
            return self.author_preview_view(context)

    def author_edit_view(self, context):
        """
        Child blocks can override this to control the view shown to authors in Studio when
        editing this block's children.
        """
        fragment = Fragment()
        self.render_children(context, fragment, can_reorder=True, can_add=False)
        return fragment

    def author_preview_view(self, context):
        """
        Child blocks can override this to add a custom preview shown to authors in Studio when
        not editing this block's children.
        """
        return self.student_view(context)
