import os
import sys
import time

import pkg_resources

from django.template import Context, Template

from selenium.webdriver.support.ui import WebDriverWait

from workbench import scenarios
from workbench.test.selenium_test import SeleniumTest


class SeleniumBaseTest(SeleniumTest):
    module_name = None
    default_css_selector = None
    relative_scenario_path = 'xml'
    timeout = 10  # seconds

    @property
    def _module_name(self):
        if self.module_name is None:
            raise NotImplementedError("Overwrite cls.module_name in your derived class.")
        return self.module_name

    @property
    def _default_css_selector(self):
        if self.default_css_selector is None:
            raise NotImplementedError("Overwrite cls.default_css_selector in your derived class.")
        return self.default_css_selector

    @property
    def scenario_path(self):
        base_dir = os.path.dirname(os.path.realpath(sys.modules[self._module_name].__file__))
        return os.path.join(base_dir, self.relative_scenario_path)

    def setUp(self):
        super(SeleniumBaseTest, self).setUp()

        # Use test scenarios
        self.browser.get(self.live_server_url)  # Needed to load tests once
        scenarios.SCENARIOS.clear()
        scenarios_list = self._load_scenarios_from_path(self.scenario_path)
        for identifier, title, xml in scenarios_list:
            scenarios.add_xml_scenario(identifier, title, xml)
            self.addCleanup(scenarios.remove_scenario, identifier)

        # Suzy opens the browser to visit the workbench
        self.browser.get(self.live_server_url)

        # She knows it's the site by the header
        header1 = self.browser.find_element_by_css_selector('h1')
        self.assertEqual(header1.text, 'XBlock scenarios')

    def wait_until_disabled(self, elem):
        wait = WebDriverWait(elem, self.timeout)
        wait.until(lambda e: not e.is_enabled(), "{} should be disabled".format(elem.text))

    def wait_until_clickable(self, elem):
        wait = WebDriverWait(elem, self.timeout)
        wait.until(lambda e: e.is_displayed() and e.is_enabled(), "{} should be cliclable".format(elem.text))

    def wait_until_text_in(self, text, elem):
        wait = WebDriverWait(elem, self.timeout)
        wait.until(lambda e: text in e.text, "{} should be in {}".format(text, elem.text))

    def go_to_page(self, page_name, css_selector=None):
        """
        Navigate to the page `page_name`, as listed on the workbench home
        Returns the DOM element on the visited page located by the `css_selector`
        """
        if css_selector is None:
            css_selector = self._default_css_selector

        self.browser.get(self.live_server_url)
        self.browser.find_element_by_link_text(page_name).click()
        time.sleep(1)
        block = self.browser.find_element_by_css_selector(css_selector)
        return block

    def _load_resource(self, resource_path):
        """
        Gets the content of a resource
        """
        resource_content = pkg_resources.resource_string(self._module_name, resource_path)
        return unicode(resource_content)

    def _render_template(self, template_path, context={}):
        """
        Evaluate a template by resource path, applying the provided context
        """
        template_str = self._load_resource(template_path)
        template = Template(template_str)
        return template.render(Context(context))

    def _load_scenarios_from_path(self, xml_path):
        list_of_scenarios = []
        if os.path.isdir(xml_path):
            for template in os.listdir(xml_path):
                if not template.endswith('.xml'):
                    continue
                identifier = template[:-4]
                title = identifier.replace('_', ' ').title()
                template_path = os.path.join(self.relative_scenario_path, template)
                scenario = unicode(self._render_template(template_path, {"url_name": identifier}))
                list_of_scenarios.append((identifier, title, scenario))
        return list_of_scenarios
