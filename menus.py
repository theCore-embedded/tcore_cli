#!/usr/bin/env python
# encoding: utf-8

import json
import npyscreen, curses
import re
import sys
import abc
import copy
import sre_yield_mod
import os
import collections
import textwrap
import logging

logger = logging.getLogger('tcore_configure')
logger.setLevel(logging.DEBUG)

file_log = logging.FileHandler('/tmp/tcore_configure.log')
file_log.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s')
file_log.setFormatter(formatter)

logger.addHandler(file_log)

# Natural sort helper
def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]

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
    def create_config(self, menu_id, cfg_id, type, description, long_description=None, **kwargs):
        pass

    @abc.abstractmethod
    def update_config(self, menu_id, cfg_id, depender=None, description=None, long_description=None, **kwargs):
        pass

    @abc.abstractmethod
    def delete_config(self, menu_id, cfg_id):
        pass

class engine:
    def __init__(self, ui_instance, schema_path, output_cfg = {}):
        schema_path = os.path.abspath(schema_path)
        fl = open(schema_path, 'r')
        self.ui_instance = ui_instance
        self.items_data = {}
        self.config_params = json.load(fl)
        self.output_cfg = output_cfg
        self.schema_path = schema_path

        root_menu_id = '/'
        self.ui_instance.set_engine(self)

        self.items_data[root_menu_id] = {
            'item_type': 'menu',
            'name': None,
            'data': self.config_params,
            'p_menu': None,
            'container': self.output_cfg
        }

        self.ui_instance.create_menu(None, root_menu_id, 'Welcome to theCore')
        self.process_menu(None, root_menu_id, self.config_params, self.output_cfg)

    def on_config_change(self, menu_id, cfg_id, **kwargs):
        if cfg_id in self.items_data:
            p_menu = self.items_data[menu_id]['p_menu']
            menu_params = self.items_data[menu_id]['data']
            normalized_name = self.items_data[menu_id]['name']

            # If no name present - dealing with top-level menu
            output_obj = self.items_data[menu_id]['container'][normalized_name] \
                if normalized_name else self.items_data[menu_id]['container']
            v = self.items_data[cfg_id]

            if menu_id == v['menu']:
                src_cfg_name = v['name']

                if v['item_type'] == 'selector':
                    self.handle_table_configurations(new_selector_values=kwargs['value'],
                        selector_id=cfg_id, selector_data=v, menu_id=menu_id,
                        menu_params=menu_params, src_cfg_name=src_cfg_name)

                v['container'][src_cfg_name] = kwargs['value']

                # Re-calculate and update menu accordingly
                self.process_menu(p_menu, menu_id, menu_params, output_obj)
                self.rebuild_config_links()
                # Resulting
                self.update_linked_configs(cfg_id)

    # Manages configurations grouped in tables
    def handle_table_configurations(self, new_selector_values, menu_id, selector_id, selector_data, menu_params, src_cfg_name):
        # Create pseudo-menu for every value selected
        # (could be one or more)

        values = new_selector_values
        if not isinstance(values, list):
            values = [ values ]

        # Prepare list of already created menu related to this selector
        already_created = [ v['selected'] for k, v in self.items_data.items() \
            if 'selector' in v and v['selector'] == selector_id ]
        # Items that should be deleted
        to_delete = [ x for x in already_created if x not in values ]

        for val in to_delete:
            # TODO: resolve duplication
            pseudo_name = 'menu-{}'.format(val)
            # Clever way to delete a menu: during menu traversal,
            # dependency resolve will fail thus forcing menu to be
            # deleted.
            menu_params[pseudo_name]['depends_on'] = '0 == 1'

        for val in values:
            pseudo_name = 'menu-{}'.format(val)
            pseudo_data = {
                'description': '{} configuration'.format(val),
            }
            new_menu_id = '{}{}-pseudo/'.format(menu_id, pseudo_name)

            if val in already_created:
                # Already created
                continue

            # Inject rest of the configuration data. Inject by
            # deepcopy is required to avoid cross-talk between entries
            # in a table
            pseudo_data.update(copy.deepcopy(menu_params[src_cfg_name]['items']))

            # There can be a configuration, depended on selected key.
            # TODO: use regex instead of simple string comparsion
            for k, v in menu_params[src_cfg_name].items():
                if k.startswith('items-'):
                    pattern = k[6:]
                    if re.search(pattern, val):
                        dependent_items = 'items-{}'.format(val)
                        pseudo_data.update(copy.deepcopy(v))

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

            # Check if output object contain some data.
            # If yes - do not clear it.
            if not pseudo_name in selector_data['container']:
                # Use selector's container as new menu parent container.
                # Both selector and related menus will be on the same level.
                selector_data['container'][pseudo_name] = {}

            self.ui_instance.create_menu(menu_id, new_menu_id,
                description=pseudo_data['description'])

            self.items_data[new_menu_id] = {
                'item_type': 'menu',
                'selector': selector_id,
                'selected': val,
                'name': pseudo_name,
                'data': pseudo_data,
                'p_menu': menu_id,
                'container': selector_data['container']
            }

            self.process_menu(menu_id, new_menu_id, pseudo_data,
                selector_data['container'][pseudo_name])

            self.rebuild_config_links()
            self.update_all_linked_configs()

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

        # Selectors and classes should be saved for later use

        if 'config-class' in data:
            self.items_data[new_cfg_id]['class'] = data['config-class'].split(',')
        if 'values-from' in data:
            self.items_data[new_cfg_id]['values_from'] = data['values-from'].split(',')

        type = data['type']

        long_description = None
        if 'long-description' in data:
            long_description = data['long-description']

        if type == 'enum':
            # Single choice or multi-choice enum
            single = True
            if 'single' in data:
                single = data['single']

            values = []
            if 'values' in data:
                values = data['values']
                # If value specification is not a list, treat it as a pattern
                if not isinstance(values, list):
                    values = list(sre_yield_mod.AllStrings(values))
                    values = sorted(values, key=natural_sort_key)

            self.ui_instance.create_config(menu_id, new_cfg_id,
                'enum', description=data['description'],
                long_description=long_description,
                values=values, single=single, selected=selected)
        elif type == 'integer':
            self.ui_instance.create_config(menu_id, new_cfg_id,
                'integer', description=data['description'],
                long_description=long_description,
                selected=selected)
        elif type == 'string':
            self.ui_instance.create_config(menu_id, new_cfg_id,
                'string', description=data['description'],
                long_description=long_description,
                selected=selected)
        elif type == 'array':
            self.ui_instance.create_config(menu_id, new_cfg_id,
                'array', description=data['description'],
                long_description=long_description,
                selected=selected)

    # Process configuration classes and update configuration data with
    # correct dependee references
    def rebuild_config_links(self):
        src_cfgs = { }
        dest_cfgs = { }

        for k, v in self.items_data.items():
            if 'class' in v:
                v['dependees'] = []
                src_cfgs[k] = v
            if 'values_from' in v:
                v['dependers'] = []
                dest_cfgs[k] = v

        for src, src_data in src_cfgs.items():
            for dest, dest_data in dest_cfgs.items():
                # Find a match between a class and a value selector
                if not set(src_data['class']).isdisjoint(dest_data['values_from']):
                    # Create a link
                    if not dest in src_data['dependees']:
                        src_data['dependees'] += [dest]
                    if not src in dest_data['dependers']:
                        dest_data['dependers'] += [src]

    # Updates all linked configurations
    def update_all_linked_configs(self):
        for k in self.items_data:
            self.update_linked_configs(k)

    # Updates linked configurations from given source config
    def update_linked_configs(self, src_cfg_id):
        if 'dependees' in self.items_data[src_cfg_id]:
            deps = self.items_data[src_cfg_id]['dependees']
            menu_id = self.items_data[src_cfg_id]['menu']

            # Every dependee must be updated.
            for d in deps:
                d_menu_id = self.items_data[d]['menu']
                clear_data = self.ui_instance.update_config(d_menu_id, d,
                    depender={'menu_id': menu_id, 'cfg_id': src_cfg_id})

                # Clear output data, in case if value lies out of domain.
                # User will be forced to enter new values.
                if clear_data:
                    name = self.items_data[d]['name']
                    self.items_data[d]['container'][name] = []

    # Processes menu, creating and deleting configurations when needed
    def process_menu(self, p_menu_id, menu_id, menu_params, output_obj):
        # Internal helper to find item by normalized key
        def is_created(name, data):
            # If no ID is assigned - no config/menu is created yet
            return 'internal_id' in data

        # Internal helper to check if output object was created or not
        def is_output_created(name, data):
            return name in output_obj

        # Possible ways to handle items
        create_item = 0
        skip_item = 1
        delete_item = 2

        # Gets decision on what do with the item: create, delete, or skip
        def get_decision(k, v):
            decision = None
            # Is item has a dependency?
            if 'depends_on' in v:
                # Is dependency satisfied?
                if self.eval_depends(v['depends_on'], menu_id):
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

            return decision

        # Pre-process include files.
        for k in list(menu_params.keys()):
            if k.startswith('include-'):
                v = menu_params[k]
                path = ''
                # Check for nested includes
                if 'internal_origin' in v and v['ref'][0] != '/':
                    origin_item = v['internal_origin']
                    src_path = self.items_data[origin_item]['path']
                    path = os.path.normpath(os.path.dirname(src_path) + '/' + v['ref'])
                else:
                    path = os.path.normpath(os.path.dirname(self.schema_path) + '/' + v['ref'])

                decision = get_decision(k, v)
                inc_id = menu_id + k + '/'

                if decision == create_item:
                    self.items_data[inc_id] = {
                        'menu': menu_id,
                        'p_menu': p_menu_id,
                        'item_type': 'include',
                        'path': path,
                        'name': k,
                        'data': v,
                    }

                    # To notify that include is already resolved
                    v['internal_id'] = inc_id

                    # Add dict object after the incldue
                    inc = json.load(open(path, 'r'))

                    # Every menu or include directive must be aware of its origin
                    def set_origin(obj, origin):
                        for k, v in obj.items():
                            if k.startswith('menu-') or k.startswith('include-'):
                                v['internal_origin'] = origin

                            if isinstance(v, dict):
                                set_origin(v, origin)

                    set_origin(inc, inc_id)

                    # Save keys in case deletion will be requested
                    self.items_data[inc_id]['inc_items'] = inc.keys()
                    menu_params.update(inc)
                elif decision == delete_item:
                    # Set false dependency on every dependent item,
                    # so they will be deleted.

                    for to_delete in self.items_data[inc_id]['inc_items']:
                        menu_params[to_delete]['depends_on'] = '1 == 0'

                    # Pop internal ID from this include
                    v.pop('internal_id', None)

        # Pre-process table configuration, to make sure pseudo-menus are created where
        # needed
        for k in list(menu_params.keys()):
            if k.startswith('table-'):
                v = menu_params[k]
                decision = get_decision(k, v)
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

                        # Is there any default value present? If so - use it
                        if 'default' in v:
                            selected = v['default']
                    else:
                        selected = output_obj[k]

                    # Inject the internal menu ID into the source config,
                    # for convenience
                    v['internal_id'] = new_selector_id

                    self.handle_config_creation(p_menu_id, menu_id, new_selector_id,
                            k, key_data, 'selector', output_obj, selected)

                    # Some items are pre-selected, thus pseudo-menus
                    # must be created right here
                    if selected != None:
                        self.handle_table_configurations(selected, menu_id,
                            new_selector_id, self.items_data[new_selector_id],
                            menu_params, k)

        # Process rest of the items (non-table)
        for k, v in menu_params.items():
            if not k.startswith('config-') and not k.startswith('menu-'):
                continue # Skip not interested fields

            decision = get_decision(k, v)

            if k.startswith('config-'):
                # Create, skip, delete config

                if decision == create_item:
                    selected = None
                    if not is_output_created(k, v):
                        # Initialize empty config, later UI will publish
                        # changes to it
                        output_obj[k] = {}

                        # Is there any default value present? If so - use it
                        if 'default' in v:
                            selected = v['default']
                            output_obj[k] = selected

                    else:
                        selected = output_obj[k]

                    # No backslash at the end means it is a config
                    new_config_id = menu_id + k

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

            elif k.startswith('menu-'):
                # Create, skip, delete menu
                if decision == create_item:
                    long_description = v['long-description'] if 'long-description' in v else None
                    new_menu_id = menu_id + k + '/'
                    self.ui_instance.create_menu(menu_id, new_menu_id,
                        description=v['description'], long_description=long_description)

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

                    self.ui_instance.delete_menu(target_menu_id)
                    self.items_data.pop(target_menu_id, None)

                    # TODO: sanitize sub-menus (challenge: root menu don't have p_menu_id)

                    # Delete all configs' internal IDs, to prevent them
                    # to be treated as created
                    def delete_internal_id(val):
                        val.pop('internal_id', None)
                        for nested in val.values():
                            if isinstance(nested, dict):
                                delete_internal_id(nested)

                    delete_internal_id(v)

                    # Sanitize all configs: delete configuration without menu
                    to_delete = [ item_id for item_id, item_v in self.items_data.items() \
                        if item_v['item_type'] == 'config' and not item_v['menu'] in self.items_data ]

                    for k in to_delete:
                        del self.items_data[k]

                elif decision == skip_item:
                    pass # Nothing to do

    # Gets output configuration
    def get_output(self):
        # Deletes all empty items, results in cool compacct configuration
        def sanitize(v):
            items = list(v.keys())
            for item in items:
                if isinstance(v[item], dict):
                    sanitize(v[item])

                # Delete item, if empty
                if isinstance(v[item], collections.Iterable) and not any(v[item]):
                    del v[item]

        sanitize(self.output_cfg)

        return self.output_cfg

    # Helper routine to get dict value using path
    def get_json_val(self, dict_arg, path):
        val=dict_arg
        for it in path.split('/')[1:]:
            # Pseudo menus are placed without suffix in output configuration
            if it.endswith('-pseudo'):
                it = it[:-7]

            val = val[it]

        return val

    # Evaluates "depends" expression
    def eval_depends(self, depends_str, current_container):
        try:
            s=re.search(r'(.*?)\s+(==|!=|>=|<=|>|<)\s+(.*)', depends_str)
            path = s[1]
            if path[0] != '/':
                path = current_container + path

            logger.debug('resolving dependency: {} {} {}'.format(path, s[2], s[3]))

            val=self.get_json_val(self.output_cfg, path)

            logger.debug('got val: {}'.format(val))

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

# Widget to enter integers
class npyscreen_int_widget(npyscreen.wgtitlefield.TitleText):
    def make_contained_widgets(self):
        # Make all widgets before changing handlers
        super().make_contained_widgets()

        # Drop old handler
        self.entry_widget.remove_complex_handler(self.entry_widget.t_input_isprint)

        # Place new handler, that will filter user input
        self.entry_widget.add_complex_handlers([
                [self.entry_widget.t_input_isprint, self.h_add_num]
            ])

    def h_add_num(self, inp):
        self.entry_widget.h_addch(inp)

        if self.entry_widget.editable:
            # Current position points to the last symbol,
            cur_pos = self.entry_widget.cursor_position
            val = self.entry_widget.value

            # No string to edit
            if len(val) == 0:
                return

            # Test that value can be converted
            try:
                v = int(val[cur_pos - 1])
            except:
                self.entry_widget.h_delete_left(None)

# Option to enter integers
class npyscreen_int_option(npyscreen.apOptions.Option):
    WIDGET_TO_USE = npyscreen_int_widget

class npyscreen_multiline(npyscreen.MultiLineAction):
    def __init__(self, *args, **kwargs):
        self.ui=kwargs['ui']
        self.f_id=kwargs['f_id']
        super().__init__(*args, **kwargs)

    def actionHighlighted(self, act_on_this, key_press):
        self.ui.on_item_selected(self.f_id, act_on_this)

class npyscreen_mainscreen(npyscreen.ActionFormMinimal):
    # Change OK button text
    OK_BUTTON_TEXT='Exit'
    def __init__(self, *args, **kwargs):
        self.metadata=kwargs['metadata']
        self.project_path=kwargs['project_path']
        super().__init__(*args, **kwargs)

    class load_cfg_button(npyscreen.ButtonPress):
        def __init__(self, *args, **kwargs):
            self.cfg_file=kwargs['cfg_file']
            self.target_name=kwargs['target_name']
            self.project_path=kwargs['project_path']
            super().__init__(*args, **kwargs)

        def whenPressed(self):
            self.parent.user_action = 'load_cfg'
            self.parent.selected_file = os.path.normpath(self.project_path + '/' + self.cfg_file)
            self.parent.selected_target = self.target_name
            # Close whole form
            self.parent.editing = False

    class new_cfg_button(npyscreen.ButtonPress):
        def __init__(self, *args, **kwargs):
            self.project_path=kwargs['project_path']
            super().__init__(*args, **kwargs)

        def whenPressed(self):
            # file_name = npyscreen.selectFile(must_exist=False,sort_by_extension=True)
            f = npyscreen.ActionPopup(name = "New target and config creation")
            cfg_wgt = f.add(npyscreen.TitleText, name = "Config name")
            tgt_wgt = f.add(npyscreen.TitleText, name = "Target name")
            f.edit()

            cfg_name = cfg_wgt.value
            tgt_name = tgt_wgt.value

            if os.path.isfile(os.path.normpath(self.project_path + '/' + cfg_name)):
                npyscreen.notify_confirm('File {} is already exists, please select another name'.format(cfg_name),
                    title='File already exists')
            elif not cfg_name or len(cfg_name) == 0:
                npyscreen.notify_confirm('Invalid configuration file name',
                    title='Invalid file name')
            elif not tgt_name or len(tgt_name) == 0:
                npyscreen.notify_confirm('Invalid target name',
                    'Invalid target name')
            else:
                self.parent.user_action = 'new_cfg'
                self.parent.selected_file = cfg_name
                self.parent.selected_target = tgt_name
                # Create new metafile
                self.parent.metadata[tgt_name] = { 'config': cfg_name }
                # Close whole form
                self.parent.editing = False

    def create(self):
        self.user_action = ''
        self.selected_file = ''
        self.selected_target = ''

        for target, data in self.metadata['targets'].items():
            cfg_file = data['config']
            description = data['description']
            btn_name = 'Edit {} ({})'.format(description, cfg_file)
            self.add(npyscreen_mainscreen.load_cfg_button, name=btn_name,
                target_name=target, cfg_file=cfg_file, project_path=self.project_path)

        btn_name = 'Add new configuration'
        self.add(npyscreen_mainscreen.new_cfg_button, name=btn_name,
            project_path=self.project_path)

    def on_ok(self):
        exit(0)

class npyscreen_form(npyscreen.ActionFormV2WithMenus):
    OK_BUTTON_TEXT='Save & Exit'
    CANCEL_BUTTON_TEXT='Exit'
    CANCEL_BUTTON_BR_OFFSET=(2,20)

    def __init__(self, *args, **kwargs):
        self.my_f_id = kwargs['my_f_id']
        self.ui = kwargs['ui']

        super().__init__(*args, **kwargs)

    def create(self):
        pass

    def adjust_widgets(self, *args, **kwargs):
        self.ui.check_widgets(self.my_f_id)

    def on_ok(self):
        out = self.ui.engine.get_output()
        f = open(self.ui.path, 'w')
        f.truncate()
        json.dump(out, f, indent=4)

        if self.ui.user_action == 'new_cfg':
            f = open(self.ui.metafile, 'w')
            json.dump(self.ui.metadata, f, indent=4)

        exit(0)

#-------------------------------------------------------------------------------

class npyscreen_ui(abstract_ui):
    def __init__(self, npyscreen_app, root_cfg_path, project_path):
        self.menu_forms = {}
        self.npyscreen_app = npyscreen_app
        self.engine = None
        self.user_action = ''

        self.metafile = os.path.normpath(project_path + '/meta.json')
        logger.debug('looking up for metafile: ' + self.metafile)
        self.metadata = json.load(open(self.metafile, 'r'))

        schema_path = root_cfg_path

        # TODO: use configurable theme
        # npyscreen.setTheme(npyscreen.Themes.BlackOnWhiteTheme)

        form_name = self.metadata['name'] + ' configuration'

        # First form to select existing configuration
        f = self.npyscreen_app.addForm('MAIN', npyscreen_mainscreen,
            name=form_name, metadata=self.metadata, project_path=project_path)
        f.edit()

        # Calculate dimensions
        # TODO: enforce:
        # min cols -> 80
        # min rows -> 24

        cols = f.columns
        rows = f.lines
        middle = int(f.columns / 2)
        rely = 2
        border = 3

        help_width = 24
        help_relx = -help_width - border
        options_width = cols - 2 * border - help_width

        # Snap help screen to middle, if size allows.
        # Option list will fit into less than 50 symbols, I hope
        if middle > 60:
            help_relx = middle
            options_width = 60
            help_width = cols - middle - 4

        self.help_width = help_width
        self.help_relx = help_relx
        self.options_width = options_width
        self.rely = rely
        self.rows = rows
        self.cols = cols

        self.user_action = f.user_action
        self.path = f.selected_file
        self.selected_target = f.selected_target

        output_cfg = {}

        # Check if existing configuration is indeed selected by user
        if self.user_action == 'load_cfg':
            output_cfg = json.load(open(self.path, 'r'))

        self.create_menu(None, 'MAIN', 'theCore configurator')
        self.engine = engine(self, schema_path=schema_path, output_cfg=output_cfg)

    def set_engine(self, engine):
        self.engine = engine

    def create_menu(self, p_menu_id, menu_id, description, long_description=None):
        # If form name is not MAIN and parent ID is not set,
        # then engine trying to create top-level menu.
        if p_menu_id == None and menu_id != 'MAIN':
            p_menu_id = 'MAIN'

        f = self.npyscreen_app.addForm(menu_id, npyscreen_form,
            name=description, my_f_id=menu_id, ui=self)

        help = f.add(npyscreen.MultiLineEdit, value='Help screen',
                max_height=self.rows-self.rely-5,
                max_width=self.help_width, relx=self.help_relx,
                rely=self.rely)
        ms = f.add(npyscreen.OptionListDisplay, name="Option List",
                values = npyscreen.OptionList().options,
                scroll_exit=True,
                begin_entry_at=14,
                max_height=self.rows-self.rely-5, max_width=self.options_width, rely=self.rely)

        self.menu_forms[menu_id] = {
            'parent': p_menu_id,
            'form': f,
            'config_widget': ms,
            'description': description,
            'long_description': long_description,
            'help-widget': help,
            'current_line': -1,
        }

        # Empty configuration dict, will be populated in create_config() function
        self.menu_forms[menu_id]['config_fields'] = {}
        self.menu_forms[menu_id]['nav_link_fwd'] = []
        self.menu_forms[menu_id]['nav_link_back'] = []

        if p_menu_id:
            self.menu_forms[p_menu_id]['nav_link_fwd'].append(
                npyscreen_switch_form_option(target_form=menu_id,
                    name='>>> Go to ', value=description, app=f.parentApp),
            )

            self.menu_forms[menu_id]['nav_link_back'] = [
                npyscreen_switch_form_option(target_form=p_menu_id,
                    name='<<< Back to ',
                    value=self.menu_forms[p_menu_id]['description'],
                    app=f.parentApp),
            ]

            self.update_form(p_menu_id)

    def delete_menu(self, menu_id):
        # Delete all links to this form
        for f_id, f_data in self.menu_forms.items():
            f_data['nav_link_fwd'] = \
                [ nav for nav in f_data['nav_link_fwd'] if nav.target_form != menu_id ]

        # Update parent form afterwards
        parent = self.menu_forms[menu_id]['parent']

        self.menu_forms.pop(menu_id, None)
        self.npyscreen_app.removeForm(menu_id)
        self.update_form(parent)

    def create_config(self, menu_id, cfg_id, type, description, long_description=None, **kwargs):
        fields = self.menu_forms[menu_id]['config_fields']
        fields[cfg_id] = {
            'form': menu_id,
            'type': type,
            'description': description,
            'long_description': long_description,
        }

        # Do a wrap, with maximum width of total form length
        long_list = None
        if long_description:
            long_list = []
            # 10 is darn arbitrary number
            wrapper = textwrap.TextWrapper(replace_whitespace=False, width=self.cols-10)
            # Arbitrary 10 here. Totally random number.
            long_descr = ' '.join(long_description).splitlines()
            for s in long_descr:
                long_list += wrapper.wrap(s)

        selected = None
        if 'selected' in kwargs:
            selected = kwargs['selected']

        if type == 'array':
            add_ctrl_id = 'array-control-add/' + cfg_id
            add_ctrl_descr = 'Add array item...'
            add_ctrl_long = 'Adds item into the \'{}\' array'.format(description)

            fields[add_ctrl_id] = {
                'form': menu_id,
                'type': 'array-control-add',
                'description': add_ctrl_descr,
                'long_description': [ add_ctrl_long ],
                'dependee': cfg_id,
                'last-value': ''
            }

            fields[add_ctrl_id]['option'] = \
                npyscreen.OptionFreeText(add_ctrl_descr, documentation=[ add_ctrl_long ])
            fields[cfg_id]['option'] = \
                npyscreen.OptionMultiChoice(description, choices=selected, documentation=long_list)
            fields[cfg_id]['array-control-parent'] = add_ctrl_id
            fields[cfg_id]['last-value'] = []

        elif type == 'enum':
            fields[cfg_id]['single'] = kwargs['single']
            if kwargs['single']:
                fields[cfg_id]['option'] = \
                    npyscreen.OptionSingleChoice(description, choices=kwargs['values'],
                        documentation=long_list)

                # Change value a bit, to fit npyscreen needs
                if selected != None:
                    selected = [ selected ]
            else:
                fields[cfg_id]['option'] = \
                    npyscreen.OptionMultiChoice(description, choices=kwargs['values'])
            fields[cfg_id]['last-value'] = []
        elif type == 'integer':
            fields[cfg_id]['option'] = \
                npyscreen_int_option(description)
            fields[cfg_id]['last-value'] = ''
        else:
            fields[cfg_id]['option'] = \
                npyscreen.OptionFreeText(description)
            fields[cfg_id]['last-value'] = ''

        if selected:
            fields[cfg_id]['option'].value = selected
            fields[cfg_id]['last-value'] = selected

        self.update_form(menu_id)

    def update_config(self, menu_id, cfg_id, depender=None, description=None, long_description=None, **kwargs):
        if depender:
            src_menu_id = depender['menu_id']
            src_cfg_id = depender['cfg_id']

            src_field = self.menu_forms[src_menu_id]['config_fields'][src_cfg_id]
            dest_field = self.menu_forms[menu_id]['config_fields'][cfg_id]

            values = src_field['option'].value
            dest_field['option'].choices = values

            # When some fields are deleted, the selection must be reset
            if set(dest_field['option'].value).difference(values):
                dest_field['option'].value = []
                return True

        return False

    def delete_config(self, menu_id, cfg_id):
        fields = self.menu_forms[menu_id]['config_fields']
        if 'array-control-parent' in fields[cfg_id]:
            control_id = fields['array-control-parent']
            fields.pop(control_id, None)

        fields.pop(cfg_id, None)
        self.update_form(menu_id)

    # Private method, updates form
    def update_form(self, f_id):
        Options = npyscreen.OptionList()
        options = Options.options
        fields = self.menu_forms[f_id]['config_fields']
        fwd_navs = self.menu_forms[f_id]['nav_link_fwd']
        back_navs = self.menu_forms[f_id]['nav_link_back']
        # To preserve order
        navs = fwd_navs + back_navs

        for link in navs:
            options.append(link)

        for id, data in fields.items():
            options.append(data['option'])

        self.menu_forms[f_id]['config_widget'].values = options

        # Help must be loaded, too, but it is unclear where to get it.
        if len(navs) > 0:
            descr = self.get_help_from_navlink(navs[0])
            self.menu_forms[f_id]['help-widget'].value = descr
        elif len(fields) > 0:
            descr = self.get_help_from_field(list(fields.values())[0])
            self.menu_forms[f_id]['help-widget'].value = descr

        # This method is heavy, but redraws entire screen without glitching
        # option list itself (as .display() does)
        self.menu_forms[f_id]['form'].DISPLAY()

    # Private method, gets help from navlink data
    def get_help_from_navlink(self, nav):
        target_f_id = nav.target_form
        descr = nav.value + '\n'

        if self.menu_forms[target_f_id]['long_description']:
            wrapper = textwrap.TextWrapper(replace_whitespace=False, width=self.help_width)
            descr += '\n'
            long_descr = ' '.join(self.menu_forms[target_f_id]['long_description']).splitlines()

            # Description must span all avaliable space
            for s in long_descr:
                descr += '\n'
                descr += wrapper.fill(s)

        return descr

    # Private method, gets help from configuration field data
    def get_help_from_field(self, field):
        descr = field['description'] + '\n'
        if field['long_description']:
            wrapper = textwrap.TextWrapper(replace_whitespace=False, width=self.help_width)
            descr += '\n'
            long_descr = ' '.join(field['long_description']).splitlines()
            # Description must span all avaliable space
            for s in long_descr:
                descr += '\n'
                descr += wrapper.fill(s)

        return descr

    # Private method, checks if there are any updates on form widgets
    def check_widgets(self, f_id):
        f = self.menu_forms[f_id]
        fields = f['config_fields']

        # Update help, if needed

        cur_line = f['config_widget'].cursor_line
        if cur_line != f['current_line']:
            # It is probable that line number is invalid, in case if no
            # widgets are placed in optionlist
            try:
                cur_opt = f['config_widget'].values[cur_line]
            except:
                return

            f['current_line'] = cur_line

            # Current option widget can be present either in configuration
            # or in navlinks.

            # Check navlinks first
            navs = self.menu_forms[f_id]['nav_link_fwd'] + self.menu_forms[f_id]['nav_link_back']
            if cur_opt in navs:
                descr = self.get_help_from_navlink(cur_opt)

                f['help-widget'].value = descr
                f['help-widget'].display()
                return

            for data in fields.values():
                if data['option'] == cur_opt:
                    descr = self.get_help_from_field(data)

                    f['help-widget'].value = descr
                    f['help-widget'].display()

        # Update dependent widget from array controls. This must be done
        # before actual update report will be executed to avoid missing data.
        for cfg_id in list(fields.keys()):
            data = fields[cfg_id]

            if data['last-value'] != data['option'].value:
                # Check if control widget was modified.
                # If so, dependent widget must be updated, too
                if fields[cfg_id]['type'] == 'array-control-add':
                    value=data['option'].value
                    depednee = fields[fields[cfg_id]['dependee']]

                    logger.debug('control widget {} updated with values: {}' \
                        .format(cfg_id, str(value)))

                    # New value for depended widget
                    if value in depednee['option'].choices:
                        # Ignore
                        continue

                    depednee['option'].choices += [ value ]
                    depednee['option'].value = depednee['option'].choices
                    depednee['last-value'] = ''

                    # Reset control widget value
                    data['option'].value = ''

                    f['config_widget'].display()

        # Update configs, if needed. They can be changed 'on fly', so keys
        # must be copied, instead of iterating dict itself
        for cfg_id in list(fields.keys()):
            # Suppose that during traversal some widgets get deleted.
            # Thus they will be missing in our list
            if not cfg_id in fields:
                continue

            data = fields[cfg_id]
            if data['last-value'] != data['option'].value:
                # Report one config at a time
                value=data['option'].value

                logger.debug('widget {} values changed old: {}, new: {}' \
                    .format(cfg_id, data['last-value'], value))

                data['last-value'] = value

                if 'array-control-parent' in data:
                    # Keep total items in sync with selected items
                    data['option'].choices = value

                if value:
                    if data['type'] == 'enum':
                        if data['single']:
                            # Normalize a value
                            value=value[0]

                self.engine.on_config_change(f_id, cfg_id, value=value)

#-------------------------------------------------------------------------------

class theCoreConfiguratorApp(npyscreen.NPSAppManaged):
    def __init__(self, root_cfg_path, project_path, *args, **kwargs):
        self.root_cfg_path = os.path.normpath(root_cfg_path)
        self.project_path = os.path.normpath(project_path)
        super().__init__(*args, **kwargs)

    def onStart(self):
        self.ui = npyscreen_ui(self, self.root_cfg_path, self.project_path)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
    App=theCoreConfiguratorApp(os.path.normpath(os.sys.argv[1]), '.')
    App.run()
