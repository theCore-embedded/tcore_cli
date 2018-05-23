#!/usr/bin/env python
# encoding: utf-8

import json
import npyscreen, curses
import re
import sys
import abc
import copy

params_json=json.loads('''{
    "menu-platform": {
        "description": "Platform configuration menu",

        "config-name": {
            "description": "Desired platform",
            "type": "enum",
            "values": ["host", "stm32"]
        },

        "config-clock": {
            "type": "integer",
            "description": "Desired clock",
            "long_description": "The clock can be configured for STM32F4 device only"
        },

        "table-drivers": {
            "description": "Desired drivers",
            "key": "config-name",
            "items": {
                "config-name": {
                    "type": "enum",
                    "values": [ "dev0", "dev1", "dev2" ],
                    "description": "Device name",
                    "single": false
                },
                "config-alias": {
                    "type": "string",
                    "description": "Device driver C++ alias"
                },
                "config-comment": {
                    "type": "string",
                    "description": "Device driver C++ comment"
                }
            }
        },

        "menu-stm32": {
            "description": "STM32 configuration menu",

            "depends_on": "/menu-platform/config-name == 'stm32'",

            "config-device": {
                "type": "enum",
                "values": ["STM32F4", "STM32L4"],
                "description": "Desired device1"
            },
            "config-device2": {
                "type": "enum",
                "values": ["STM32F4", "STM32L4"],
                "description": "Desired device2"
            },
            "config-device3": {
                "type": "enum",
                "values": ["STM32F4", "STM32L4"],
                "description": "Desired device3"
            },
            "config-device44": {
                "type": "enum",
                "values": ["STM32F4", "STM32L4"],
                "description": "Desired device4"
            },

            "config-clock": {
                "type": "integer",
                "depends_on": "/menu-platform/menu-stm32/config-device == 'STM32F4'",
                "description": "Desired clock",
                "long_description": "The clock can be configured for STM32F4 device only"
            },

            "table-uart": {
                "description": "UART configuration table",
                "key": "config-channel",
                "items": {
                    "config-channel": {
                        "type": "enum",
                        "values": [ "UART0", "UART1", "UART2" ],
                        "description": "Desired UART",
                        "single": false
                    },
                    "config-baud": {
                        "type": "enum",
                        "default": 115200,
                        "values": [ 115200, 9600 ],
                        "description": "UART baud rate"
                    },
                    "config-alias": {
                        "type": "string",
                        "description": "UART driver C++ alias"
                    },
                    "config-comment": {
                        "type": "string",
                        "description": "UART driver C++ comment"
                    }
                }
            }
        }
    }
}''')

cfg_json={}

#-------------------------------------------------------------------------------

class abstract_ui(abc.ABC):
    @abc.abstractmethod
    def set_engine(self, engine):
        pass

    @abc.abstractmethod
    def create_menu(self, menu_id):
        pass

    @abc.abstractmethod
    def delete_menu(self, menu_id):
        pass

    @abc.abstractmethod
    def create_config(self, menu_id, id, type, description, long_description=None, **kwargs):
        pass

    @abc.abstractmethod
    def delete_config(self, menu_id, id):
        pass

class engine:
    def __init__(self, ui_instance):
        self.ui_instance = ui_instance
        self.items_data = {}
        self.config_params = params_json
        self.output_cfg = cfg_json

        # Root form must be named as 'MAIN'
        root_menu_id = 'MAIN'
        self.ui_instance.set_engine(self)
        self.ui_instance.create_menu(None, root_menu_id, 'Welcome to theCore configurator')
        self.process_menu(None, root_menu_id, self.config_params, self.output_cfg)

    def on_config_change(self, menu_id, id, **kwargs):
        if id in self.items_data:

            p_menu = self.items_data[menu_id]['p_menu']
            menu_params = self.items_data[menu_id]['data']
            normalized_name = self.items_data[menu_id]['name']
            output_obj = self.items_data[menu_id]['container'][normalized_name]
            v = self.items_data[id]

            if menu_id == v['menu']:
                src_cfg_name = v['name']

                if v['item_type'] == 'config':
                    v['container'][src_cfg_name] = kwargs['value']
                elif v['item_type'] == 'selector':
                    # Create pseudo-menu for every value selected
                    # (could be one or more)

                    values = kwargs['value']
                    if not isinstance(values, list):
                        values = [ values ]

                    # Prepare list of already created menu related to this selector
                    already_created = [ v['selected'] for k, v in self.items_data.items() \
                        if 'selector' in v and v['selector'] == id ]
                    # Items that should be deleted
                    to_delete = [ x for x in already_created if x not in values ]

                    for val in to_delete:
                        # TODO: resolve duplication
                        pseudo_name = 'menu-' + val
                        # Clever way to delete a menu: during menu traversal,
                        # dependency resolve will fail thus forcing menu to be
                        # deleted.
                        menu_params[pseudo_name]['depends_on'] = '0 == 1'

                    for val in values:
                        pseudo_name = 'menu-' + val
                        pseudo_data = {
                            'description': val + ' configuration',
                        }
                        new_menu_id = '{}/{}-pseudo/'.format(menu_id, pseudo_name)

                        if val in already_created:
                            # Already created
                            continue

                        # Inject rest of the configuration data. Inject by
                        # deepcopy is required to avoid cross-talk between entries
                        # in a table
                        pseudo_data.update(copy.deepcopy(menu_params[src_cfg_name]['items']))
                        # Delete duplicated key item. It resides both "outside"
                        # and "inside". Delete from "inside"
                        key_item = menu_params[src_cfg_name]['key']
                        pseudo_data.pop(key_item, None)

                        # Save internal ID
                        pseudo_data['internal_id'] = new_menu_id

                        # Inject pseudo-menus
                        menu_params[pseudo_name] = pseudo_data

                        # Replace output object and create pseudo menus
                        # BEFORE real menus will be processed.
                        # This will ensure pseudo menu data is customized
                        # as we want it.

                        # Use selector's container as new menu parent container
                        v['container'][src_cfg_name][pseudo_name] = {}

                        self.ui_instance.create_menu(menu_id, new_menu_id,
                            description=pseudo_data['description'])

                        self.items_data[new_menu_id] = {
                            'item_type': 'menu',
                            'selector': id,
                            'selected': val,
                            'name': pseudo_name,
                            'data': pseudo_data,
                            'p_menu': menu_id,
                            'container': v['container'][src_cfg_name]
                        }

                        self.process_menu(menu_id, new_menu_id, pseudo_data,
                            v['container'][src_cfg_name][pseudo_name])

                # Re-calculate and update menu accordingly

                self.process_menu(p_menu, menu_id, menu_params, output_obj)

    def handle_config_creation(self, p_menu_id, menu_id, new_cfg_id, name, data, item_type, container):

        self.items_data[new_cfg_id] = {
            'item_type': item_type,
            'name': name,
            'data': data,
            'p_menu': p_menu_id,
            'menu': menu_id,
            'container': container
        }

        # Inject the internal config ID into the source config, for convenience
        data['internal_id'] = new_cfg_id

        type = data['type']

        if type == 'enum':
            # Single choice or multi-choice enum
            single = True
            if 'single' in data:
                single = data['single']

            self.ui_instance.create_config(menu_id, new_cfg_id,
                'enum', description=data['description'],
                values=data['values'], single=single)
        elif type == 'integer':
            self.ui_instance.create_config(menu_id, new_cfg_id,
                'integer', description=data['description'])
        elif type == 'string':
            self.ui_instance.create_config(menu_id, new_cfg_id,
                'string', description=data['description'])

    # Processes menu, creating and deleting configurations when needed
    def process_menu(self, p_menu_id, menu_id, menu_params, output_obj):
        # Internal helper to find item by normalized key
        def is_created(name, data):
            # If no ID is assigned - no config/menu is created yet
            return 'internal_id' in data

        for k, v in menu_params.items():
            if not k.startswith('config-') and not k.startswith('menu-') and not k.startswith('table-'):
                continue # Skip not interested fields

            # Possible ways to handle items
            create_item = 0
            skip_item = 1
            delete_item = 2

            decision = None

            # Is item has a dependency?
            if 'depends_on' in v:
                # Is dependency satisfied?
                if self.eval_depends(v['depends_on']):
                    # Is item created?
                    if is_created(k, v):
                        # item is already created, nothing to do
                        decision = skip_item
                    else:
                        # New item should be created
                        decision = create_item
                else:
                    # Dependency is not satisfied - item shouldn't
                    # be displayed.

                    # Is item created?
                    if is_created(k, v):
                        # Item must be deleted, if present.
                        decision = delete_item
                    else:
                        # No item present, nothing to delete
                        decision = skip_item
            else:
                # Item is dependless. Meaning should be displayed
                # no matter what.

                # Is item created?
                if is_created(k, v):
                    # item is already created, nothing to do
                    decision = skip_item
                else:
                    # New item should be created
                    decision = create_item

            if k.startswith('config-'):
                # Create, skip, delete config

                if decision == create_item:
                    # Initialize empty config, later UI will publish
                    # changes to it
                    output_obj[k] = {}

                    # No backslash at the end means it is a config
                    new_config_id = menu_id + '/' + k

                    self.handle_config_creation(p_menu_id, menu_id, new_config_id,
                        k, v, 'config', output_obj)

                elif decision == delete_item:
                    # Configuration must be deleted, if present.
                    self.ui_instance.delete_config(menu_id, k)
                    output_obj.pop(k, None)
                    self.items_data.pop(v['internal_id'], None)

                elif decision == skip_item:
                    pass # Nothing to do
            elif k.startswith('table-'):
                if decision == create_item:
                    # Configuration that in fact acts as a key selector
                    key = v['key']
                    key_data = v['items'][key]
                    new_selector_id = '{}/{}-selector'.format(menu_id, k)

                    # Prepare configuration object. Selector will not push there
                    # any data. Instead, child menus will.
                    output_obj[k] = {}

                    # Inject the internal menu ID into the source config,
                    # for convenience
                    v['internal_id'] = new_selector_id

                    self.handle_config_creation(p_menu_id, menu_id, new_selector_id,
                            k, key_data, 'selector', output_obj)

            elif k.startswith('menu-'):
                # Create, skip, delete menu
                if decision == create_item:
                    new_menu_id = menu_id + '/' + k + '/'
                    self.ui_instance.create_menu(menu_id, new_menu_id,
                        description=v['description'])

                    output_obj[k] = {}
                    self.items_data[new_menu_id] = {
                        'item_type': 'menu',
                        'name': k,
                        'data': v,
                        'p_menu': menu_id,
                        'container': output_obj
                    }

                    # Inject the internal menu ID into the source config,
                    # for convenience
                    v['internal_id'] = new_menu_id

                    self.process_menu(menu_id, new_menu_id, v, output_obj[k])

                elif decision == delete_item:
                    # Delete menu first
                    target_menu_id = v['internal_id']
                    target_container = self.items_data[target_menu_id]['container']
                    target_container.pop(k, None)
                    v.pop('internal_id', None)

                    self.ui_instance.delete_menu(target_menu_id)
                    self.items_data.pop(target_menu_id, None)

                    # TODO: sanitize sub-menus (challenge: root menu don't have p_menu_id)

                    # Sanitize all configs: delete configuration without menu
                    to_delete = [ item_id for item_id, item_v in self.items_data.items() \
                        if item_v['item_type'] == 'config' and not item_v['menu'] in self.items_data ]
                    for k in to_delete:
                        del self.items_data[k]

                elif decision == skip_item:
                    pass # Nothing to do

    # Gets output configuration
    def get_output(self):
        return self.output_cfg

    # Helper routine to get dict value using path
    def get_json_val(self, dict_arg, path):
        val=dict_arg
        for it in path.split('/')[1:]:
            val=val[it]

        return val

    # Evaluates "depends" expression
    def eval_depends(self, depends_str):
        try:
            s=re.search(r'(.*?)\s+(==|!=|>=|<=|>|<)\s+(.*)', depends_str)
            val=self.get_json_val(self.output_cfg, s[1])

            # To let string be processed in eval() without errors,
            # it should be captured in quotes
            if type(val) is str:
                val='\'' + val + '\''

            expr=str(val) + s[2] + s[3]
            return eval(expr)
        except:
            return False

#-------------------------------------------------------------------------------

# Navigation line, button that leads to the given form
class npyscreen_switch_form_option(npyscreen.OptionFreeText):
    def __init__(self, *args, **kwargs):
        self.target_form=kwargs['target_form']
        self.app=kwargs['app']
        kwargs.pop('target_form', None)
        kwargs.pop('app', None)
        super().__init__(*args, **kwargs)

    def change_option(self):
        self.app.switchForm(self.target_form)

class npyscreen_multiline(npyscreen.MultiLineAction):
    def __init__(self, *args, **kwargs):
        self.ui=kwargs['ui']
        self.f_id=kwargs['f_id']
        super().__init__(*args, **kwargs)

    def actionHighlighted(self, act_on_this, key_press):
        self.ui.on_item_selected(self.f_id, act_on_this)

class npyscreen_form(npyscreen.ActionFormV2WithMenus):
    def __init__(self, *args, **kwargs):
        self.my_f_id = kwargs['my_f_id']
        self.ui = kwargs['ui']

        super().__init__(*args, **kwargs)

    def create(self):
        pass

    def adjust_widgets(self, *args, **keywords):
        self.ui.check_widgets(self.my_f_id)

class npyscreen_ui(abstract_ui):
    def __init__(self, npyscreen_app):
        self.menu_forms = {}
        self.npyscreen_app = npyscreen_app
        self.engine = None

    def set_engine(self, engine):
        self.engine = engine

    def create_menu(self, p_menu_id, menu_id, description, long_description=None):
        f = self.npyscreen_app.addForm(menu_id, npyscreen_form,
            name=description, my_f_id=menu_id, ui=self)

        debug = f.add(npyscreen.MultiLineEdit, value='', max_height=3)

        ms = f.add(npyscreen.OptionListDisplay, name="Option List",
                values = npyscreen.OptionList().options,
                scroll_exit=True,
                max_height=8)

        self.menu_forms[menu_id] = {
            'parent': p_menu_id,
            'form': f,
            'config_widget': ms,
            'debug': debug,
            'description': description,
            'long_description': long_description
        }

        # Empty configuration dict, will be populated in create_config() function
        self.menu_forms[menu_id]['config_fields'] = {}
        self.menu_forms[menu_id]['nav_link'] = []

        if p_menu_id:
            self.menu_forms[p_menu_id]['nav_link'].append(
                npyscreen_switch_form_option(target_form=menu_id,
                    name='>>> Go to ', value=description, app=f.parentApp),
            )

            self.menu_forms[menu_id]['nav_link'] = [
                npyscreen_switch_form_option(target_form=p_menu_id,
                    name='<<< Back to ',
                    value=self.menu_forms[p_menu_id]['description'],
                    app=f.parentApp),
            ]

            self.update_form(p_menu_id)

    def delete_menu(self, menu_id):
        # Delete all links to this form
        for f_id, f_data in self.menu_forms.items():
            f_data['nav_link'] = \
                [ nav for nav in f_data['nav_link'] if nav.target_form != menu_id ]

        # Update parent form afterwards
        parent = self.menu_forms[menu_id]['parent']

        self.menu_forms.pop(menu_id, None)
        self.npyscreen_app.removeForm(menu_id)
        self.update_form(parent)

    def create_config(self, menu_id, id, type, description, long_description=None, **kwargs):
        self.menu_forms[menu_id]['config_fields'][id] = {
            'form': menu_id,
            'type': type,
            'description': description,
            'long_description': long_description,
            'last_value': ''
        }

        if type == 'enum':
            if kwargs['single']:
                self.menu_forms[menu_id]['config_fields'][id]['single'] = True
                self.menu_forms[menu_id]['config_fields'][id]['option'] = \
                    npyscreen.OptionSingleChoice(description, choices=kwargs['values'])
            else:
                self.menu_forms[menu_id]['config_fields'][id]['single'] = False
                self.menu_forms[menu_id]['config_fields'][id]['option'] = \
                    npyscreen.OptionMultiChoice(description, choices=kwargs['values'])
        else:
            self.menu_forms[menu_id]['config_fields'][id]['option'] = \
                npyscreen.OptionFreeText(description)

        self.update_form(menu_id)

    def delete_config(self, menu_id, id):
        self.menu_forms[menu_id]['config_fields'].pop(id, None)
        self.update_form(menu_id)

    ''' Private method, updates form '''
    def update_form(self, f_id):
        Options = npyscreen.OptionList()
        options = Options.options

        for id, data in self.menu_forms[f_id]['config_fields'].items():
            options.append(data['option'])

        for link in self.menu_forms[f_id]['nav_link']:
            options.append(link)

        self.menu_forms[f_id]['config_widget'].values = options

        # Debug output of resulting config
        self.menu_forms[f_id]['debug'].value = str(self.engine.get_output())

        # This method is heavy, but redraws entire screen without glitching
        # option list itself (as .display() does)
        self.menu_forms[f_id]['form'].DISPLAY()

    ''' Private method, checks if there are any updates on form widgets '''
    def check_widgets(self, f_id):
        fields = self.menu_forms[f_id]['config_fields']

        for id, data in fields.items():
            if data['last_value'] != data['option'].value:
                data['last_value'] = data['option'].value
                # Report one config at a time
                value=data['option'].value
                if data['type'] == 'enum':
                    if data['single']:
                        # Normalize a value
                        value=value[0]
                self.engine.on_config_change(f_id, id, value=value)
                return

        self.update_form(f_id)

#-------------------------------------------------------------------------------

class theCoreConfiguratorApp(npyscreen.NPSAppManaged):
    def onStart(self):
        self.ui = npyscreen_ui(self)
        self.engine = engine(self.ui)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
    with open('stdout.log', 'w', 1) as fd:
        sys.stdout=fd
        App=theCoreConfiguratorApp()
        App.run()

