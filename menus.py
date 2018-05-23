#!/usr/bin/env python
# encoding: utf-8

import json
import npyscreen, curses
import re
import sys
import abc
import copy

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
    def __init__(self, ui_instance, config_params, output_cfg = {}):
        self.ui_instance = ui_instance
        self.items_data = {}
        self.config_params = config_params
        self.output_cfg = output_cfg

        root_menu_id = '/'
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
                    self.handle_table_configurations(new_keys=kwargs['value'],
                        selector_data=v, menu_id=menu_id, menu_params=menu_params,
                        src_cfg_name=src_cfg_name)

                # Re-calculate and update menu accordingly

                self.process_menu(p_menu, menu_id, menu_params, output_obj)

    # Manages configurations grouped in tables
    def handle_table_configurations(self, new_keys, menu_id, selector_data, menu_params, src_cfg_name):
        # Create pseudo-menu for every value selected
        # (could be one or more)

        values = new_keys
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
            selector_data['container'][src_cfg_name][pseudo_name] = {}

            self.ui_instance.create_menu(menu_id, new_menu_id,
                description=pseudo_data['description'])

            self.items_data[new_menu_id] = {
                'item_type': 'menu',
                'selector': id,
                'selected': val,
                'name': pseudo_name,
                'data': pseudo_data,
                'p_menu': menu_id,
                'container': selector_data['container'][src_cfg_name]
            }

            self.process_menu(menu_id, new_menu_id, pseudo_data,
                selector_data['container'][src_cfg_name][pseudo_name])

    # Creates configuration
    def handle_config_creation(self, p_menu_id, menu_id, new_cfg_id, name, data, item_type, container, selected):

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

            # Values for this configuration can be provided from elsewhere
            values = []
            if 'values-selector' in data:
                selector = data['values-selector']
                values = [ item for item in self.items_data.items() \
                    if 'value-classes' in item and selector in item['value-classes'] ]
            else:
                values = data['values']

            self.ui_instance.create_config(menu_id, new_cfg_id,
                'enum', description=data['description'],
                values=values, single=single, selected=selected)
        elif type == 'integer':
            self.ui_instance.create_config(menu_id, new_cfg_id,
                'integer', description=data['description'], selected=selected)
        elif type == 'string':
            self.ui_instance.create_config(menu_id, new_cfg_id,
                'string', description=data['description'], selected=selected)

    # Processes menu, creating and deleting configurations when needed
    def process_menu(self, p_menu_id, menu_id, menu_params, output_obj):
        # Internal helper to find item by normalized key
        def is_created(name, data):
            # If no ID is assigned - no config/menu is created yet
            return 'internal_id' in data

        # Internal helper to check if output object was created or not
        def is_output_created(name, data):
            return name in output_obj

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
                    selected = None
                    if not is_output_created(k, v):
                        # Initialize empty config, later UI will publish
                        # changes to it
                        output_obj[k] = {}
                    else:
                        selected = output_obj[k]

                    # No backslash at the end means it is a config
                    new_config_id = menu_id + '/' + k

                    self.handle_config_creation(p_menu_id, menu_id, new_config_id,
                        k, v, 'config', output_obj, selected)

                elif decision == delete_item:
                    # Configuration must be deleted, if present.
                    self.ui_instance.delete_config(menu_id, v['internal_id'])
                    self.items_data.pop(v['internal_id'], None)
                    v.pop('internal_id', None)
                    output_obj.pop(k, None)

                elif decision == skip_item:
                    pass # Nothing to do
            elif k.startswith('table-'):
                if decision == create_item:
                    # Configuration that in fact acts as a key selector
                    key = v['key']
                    key_data = v['items'][key]
                    new_selector_id = '{}/{}-selector'.format(menu_id, k)

                    selected = None
                    if not is_output_created(k, v):
                        # Prepare configuration object. Selector will not push there
                        # any data. Instead, child menus will.
                        output_obj[k] = {}
                    else:
                        selected = output_obj[k]

                    # Inject the internal menu ID into the source config,
                    # for convenience
                    v['internal_id'] = new_selector_id

                    self.handle_config_creation(p_menu_id, menu_id, new_selector_id,
                            k, key_data, 'selector', output_obj, selected)

            elif k.startswith('menu-'):
                # Create, skip, delete menu
                if decision == create_item:
                    new_menu_id = menu_id + '/' + k + '/'
                    self.ui_instance.create_menu(menu_id, new_menu_id,
                        description=v['description'])

                    if not is_output_created(k, v):
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
                        # Delete all widgets' internal IDs, to prevent them
                        # to be treated as created
                        self.items_data[k]['data'].pop('internal_id', None)
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

class npyscreen_mainscreen(npyscreen.ActionFormV2WithMenus):
    def create(self):
        pass


class npyscreen_form(npyscreen.ActionFormV2WithMenus):
    def __init__(self, *args, **kwargs):
        self.my_f_id = kwargs['my_f_id']
        self.ui = kwargs['ui']

        super().__init__(*args, **kwargs)

    def create(self):
        pass

    def adjust_widgets(self, *args, **keywords):
        self.ui.check_widgets(self.my_f_id)

    def on_ok(self):
        out = self.ui.engine.get_output()
        f = open('output.json', 'w')
        json.dump(out, f, indent=4)
        exit(0)

class npyscreen_ui(abstract_ui):
    def __init__(self, npyscreen_app):
        self.menu_forms = {}
        self.npyscreen_app = npyscreen_app
        self.engine = None

        # First form to select existing configuration
        f = self.npyscreen_app.addForm('MAIN', npyscreen_mainscreen, name='Main form')
        fs = f.add(npyscreen.TitleFilenameCombo, name="Select existing theCore configuration")
        f.edit()
        existing_file = fs.get_value()

        self.create_menu(None, 'MAIN', 'Hello, World')

        existing_cfg = {}
        if existing_file:
            existing_cfg = json.load(open(existing_file, 'r'))

        fl = open('src.json', 'r')
        src = json.load(fl)
        self.engine = engine(self, src, existing_cfg)

    def set_engine(self, engine):
        self.engine = engine

    def create_menu(self, p_menu_id, menu_id, description, long_description=None):
        # If form name is not MAIN and parent ID is not set,
        # then engine trying to create top-level menu.
        if p_menu_id == None and menu_id != 'MAIN':
            p_menu_id= 'MAIN'

        f = self.npyscreen_app.addForm(menu_id, npyscreen_form,
            name=description, my_f_id=menu_id, ui=self)

        debug = f.add(npyscreen.MultiLineEdit, value='', max_height=3)

        ms = f.add(npyscreen.OptionListDisplay, name="Option List",
                values = npyscreen.OptionList().options,
                scroll_exit=True,
                max_height=f.lines - 10)

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
        fields = self.menu_forms[menu_id]['config_fields']
        fields[id] = {
            'form': menu_id,
            'type': type,
            'description': description,
            'long_description': long_description,
            'last_value': ''
        }

        selected = None
        if 'selected' in kwargs and kwargs['selected']:
            selected = kwargs['selected']

        if type == 'enum':
            fields[id]['single'] = kwargs['single']
            if kwargs['single']:
                fields[id]['option'] = \
                    npyscreen.OptionSingleChoice(description, choices=kwargs['values'])

                # Change value a bit, to fit npyscreen needs
                if selected:
                    selected = [ selected ]
            else:
                fields[id]['option'] = \
                    npyscreen.OptionMultiChoice(description, choices=kwargs['values'])
        else:
            fields[id]['option'] = \
                npyscreen.OptionFreeText(description)

        if selected:
            fields[id]['option'].value = selected

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

#-------------------------------------------------------------------------------

if __name__ == "__main__":
    with open('stdout.log', 'w', 1) as fd:
        sys.stdout=fd
        App=theCoreConfiguratorApp()
        App.run()

