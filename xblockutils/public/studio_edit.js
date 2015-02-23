/* Javascript for StudioEditableXBlockMixin. */
function StudioEditableXBlockMixin(runtime, element) {
    "use strict";

    // //TODO: replace with django's javascript i18n utilities
    // function gettext(s) {
    //     return s;
    // }

    var fields = [];
    var tinyMceAvailable = (typeof $.fn.tinymce !== 'undefined'); // Studio includes a copy of tinyMCE and its jQuery plugin

    $(element).find('.field-data-control').each(function () {
        var $field = $(this);
        var $wrapper = $field.closest('li');
        var $resetButton = $wrapper.find('button.setting-clear');
        var type = $wrapper.data('cast');
        fields.push({
            $field: $field,
            name: $wrapper.data('field-name'),
            isSet: function () {
                return $wrapper.hasClass('is-set');
            },
            val: function () {
                var val = $field.val();
                // Cast values to the appropriate type so that we send nice clean JSON over the wire:
                if (type == 'boolean')
                    return (val == 'true' || val == '1');
                if (type == "integer")
                    return parseInt(val, 10);
                if (type == "float")
                    return parseFloat(val);
                if (type == "generic") {
                    val = val.trim();
                    if (val === "")
                        val = null;
                    else
                        val = JSON.parse(val); // TODO: handle parse errors
                }
                return val;
            }
        });
        var fieldChanged = function () {
            // Field value has been modified:
            $wrapper.addClass('is-set');
            $resetButton.removeClass('inactive').addClass('active');
        };
        $field.bind("change input paste", fieldChanged);
        $resetButton.click(function () {
            $field.val($wrapper.attr('data-default')); // Use attr instead of data to force treating the default value as a string
            $wrapper.removeClass('is-set');
            $resetButton.removeClass('active').addClass('inactive');
        });
        if (type == 'html' && tinyMceAvailable) {
            if ($field.tinymce())
                $field.tinymce().remove(); // Stale instance from a previous dialog. Delete it to avoid interference.
            $field.tinymce({
                theme: 'modern',
                skin: 'studio-tmce4',
                height: '200px',
                formats: {
                    code: {
                        inline: 'code'
                    }
                },
                codemirror: {
                    path: "" + baseUrl + "/js/vendor"
                },
                plugins: "link codemirror",
                menubar: false,
                statusbar: false,
                toolbar_items_size: 'small',
                toolbar: "formatselect | styleselect | bold italic underline forecolor wrapAsCode | bullist numlist outdent indent blockquote | link unlink | code",
                resize: "both",
                setup: function (ed) {
                    ed.on('change', fieldChanged);
                }
            });
        }
    });

    var studio_submit = function (data) {
        var handlerUrl = runtime.handlerUrl(element, 'submit_studio_edits');
        runtime.notify('save', {
            state: 'start',
            message: gettext("Saving")
        });
        $.ajax({
            type: "POST",
            url: handlerUrl,
            data: JSON.stringify(data),
            dataType: "json",
            global: false, // Disable Studio's error handling that conflicts with studio's notify('save') and notify('cancel') :-/
            success: function (response) {
                console.log("response");
                console.dir(response);
                runtime.notify('save', {
                    state: 'end'
                });
            }
        }).fail(function (jqXHR) {
            var message = gettext("This may be happening because of an error with our server or your internet connection. Try refreshing the page or making sure you are online.");
            if (jqXHR.responseText) { // Is there a more specific error message we can show?
                try {
                    message = JSON.parse(jqXHR.responseText).error;
                } catch (error) {
                    message = jqXHR.responseText.substr(0, 300);
                }
            }
            runtime.notify('error', {
                title: gettext("Unable to update settings"),
                message: message
            });
        });
    };

    $('.save-button', element).bind('click', function (e) {
        e.preventDefault();
        var values = {};
        var notSet = []; // List of field names that should be set to default values
        for (var i in fields) {
            var field = fields[i];
            if (field.isSet()) {
                values[field.name] = field.val();
            } else {
                notSet.push(field.name);
            }
        }
        studio_submit({
            values: values,
            defaults: notSet
        });
    });

    $(element).find('.cancel-button').bind('click', function (e) {
        e.preventDefault();
        runtime.notify('cancel', {});
    });
}