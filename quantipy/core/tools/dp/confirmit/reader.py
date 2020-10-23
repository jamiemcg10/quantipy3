import json
import pandas as pd
from quantipy.core.helpers.functions import load_json
from quantipy.core.tools.dp.prep import start_meta

data_json_path = "./confirmit_data.json"
meta_json_path = "./confirmit_meta.json"

def quantipy_from_confirmit(data_json, meta_json, text_key='en-GB'):
    types_translations = {
        'numeric': 'float',
        'text': 'string',
        'singleChoice': 'single',
        'multiChoice': 'delimited set' 
    }
    def create_subvar_meta(parsed_meta, subvar):
        parent_key = 'masks@' + parsed_meta['name']
        name = subvar['source'].replace('columns@', '')
        return {
            'name': name,
            'parent': {parent_key: {'type': parsed_meta['type']}},
            'text': subvar['text'],
            'type': parsed_meta['subtypes'] 
        }

    def fill_items_arr(parsed_meta):
        try:
            var_idx = columns_array.index('columns@' + parsed_meta['name'])
            for item in parsed_meta['items']:
                var_idx += 1
                columns_array.insert(var_idx, item['source'])
        except ValueError:
            var_idx = None

    def get_grid_items(variable):
        children_array = []
        for field in variable['fields']:
            children_array.append({
                'properties': {},
                'source': 'columns@' + variable['name'] + '_' + field['code'],
                'text': {'en-GB': field['texts'][0]['text']}
            })
        return children_array
        

    def get_options(variable, var_type, is_child):
        col_values_arr = []
        for value in variable:
            loopReference = value.get('loopReference')
            if(loopReference and var_type == 'single'):
                filtered_loop_ref = filter(lambda x: x['name']  == loopReference, children_vars) 
                child_var = list(filtered_loop_ref)
                col_values_val = get_main_info(child_var[0], var_type, is_child=True)
            else:
                col_values_val = value["code"]
            col_values_arr.append({"text": {"en-GB": value["texts"][0]["text"]}, "value": col_values_val})
        return col_values_arr

    def get_main_info(variable_meta, var_type, is_child=False):
        if is_child:
            variable = variable_meta.get('keys')[0]
        else:
            variable = variable_meta

        variable_obj = {
            "name": variable['name'],
            "parent": {},
            "type": var_type,
            "properties": {}
        }

        if var_type == 'array':
            variable_obj['items'] = get_grid_items(variable)
            if variable['variableType'] == 'numeric':
                variable_obj['subtypes'] = 'float'
            if variable['variableType'] == 'text':
                variable_obj['subtypes'] = 'string'
        if var_type != 'float' and var_type != 'array' and var_type != 'string':
            variable_obj['values'] = get_options(variable["options"], var_type, is_child)
        if variable.get('titles'):
            variable_obj['text'] = {"en-GB": variable['titles'][0]["text"]}
        else:
            if variable.get('texts'):
                variable_obj['text'] = {"en-GB": variable['texts'][0]["text"]}

        if is_child:
            variable_obj.update({
                'texts': variable_meta.get('texts'),
                'variables': [get_main_info(var_meta, types_translations[var_meta['variableType']]) for var_meta in variable_meta.get('variables')]
            })
        
        return variable_obj

    data_array = []
    sub_data_array = []
    columns_array = []
    with open(data_json, "r") as read_data_file:
        data_parsed = json.load(read_data_file)

    with open(meta_json, "r") as read_meta_file:
        meta_parsed = json.load(read_meta_file)

    for idx, element in enumerate(data_parsed):
        for k, v in element.items():
            if idx == 0:
                columns_array.append('columns@' + k)
            sub_data_array.append(v)
        data_array.append(sub_data_array)

    columns_output = {}
    grid_vars = []
    vars_arr = meta_parsed.get('root').get('variables')
    children_vars = meta_parsed.get('root').get('children')
    for variable in vars_arr:
        if variable['variableType'] == 'singleChoice':
            columns_output[variable['name']] = get_main_info(variable, 'single')
        if variable['variableType'] == 'multiChoice':
            columns_output[variable['name']] = get_main_info(variable, 'delimited set')
        if variable['variableType'] == 'numeric':
            if variable.get('fields'):
                parsed_meta = get_main_info(variable, 'array')
                columns_output[variable['name']] = parsed_meta
                fill_items_arr(parsed_meta)
                numeric_children_arr = []
                for subvar in parsed_meta['items']:
                    parsed_subvar_meta = create_subvar_meta(parsed_meta, subvar)
                    columns_output[parsed_subvar_meta['name']] = parsed_subvar_meta
                    numeric_children_arr.append(parsed_subvar_meta['name'])
                grid_vars.append({'parent': variable['name'], 'children': numeric_children_arr})
            else:
                columns_output[variable['name']] = get_main_info(variable, 'float')
        if variable['variableType'] == 'text':
            if variable.get('fields'):
                parsed_meta = get_main_info(variable, 'array')
                columns_output[variable['name']] = parsed_meta
                fill_items_arr(parsed_meta)
                text_children_arr = []
                for subvar in parsed_meta['items']:
                    parsed_subvar_meta = create_subvar_meta(parsed_meta, subvar)
                    columns_output[parsed_subvar_meta['name']] = parsed_subvar_meta
                    text_children_arr.append(parsed_subvar_meta['name'])
                grid_vars.append({'parent': variable['name'], 'children': text_children_arr})
            else:
                columns_output[variable['name']] = get_main_info(variable, 'string')
    
    output_obj = {
        "info": {
            "text": "Converted from SAV file .",
            "from_source": {"pandas_reader": "sav"}
        },
        "lib": {"values": {}, "default text": "main"},
        "masks": {},
        "sets": {
            "data_file": {
                "text": {"en-GB": "Variable order in source file"},
                "items": columns_array
            }
        },
        "type": "pandas.DataFrame",
        "columns": columns_output
    }
    for data in data_parsed:
        for nav in grid_vars:
            if nav['parent'] in data:
               old_values = data.pop(nav['parent'])
               for k, v in old_values.items():
                   data[nav['parent'] + '_' + k] = v

    return output_obj, data_parsed