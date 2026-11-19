#!/usr/bin/env python3
"""Audit the portable, inactive Automotive GTM export using only Python's standard library."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

CONTAINER_NAME = 'Sophos Automotive Marketing GTM Container'
HOSTNAME = 'template-not-installed.invalid'
FAMILIES = ('tag', 'trigger', 'variable', 'builtInVariable')
ENTITY_KEYS = {
    'tag': {'tagId', 'name', 'type', 'parameter', 'firingTriggerId', 'blockingTriggerId',
            'tagFiringOption', 'paused', 'monitoringMetadata', 'consentSettings'},
    'trigger': {'triggerId', 'name', 'type', 'customEventFilter', 'filter'},
    'variable': {'variableId', 'name', 'type', 'parameter', 'formatValue'},
    'builtInVariable': {'name', 'type'},
}
IDS = {'tag': 'tagId', 'trigger': 'triggerId', 'variable': 'variableId'}
COUNTS = {'tag': 38, 'trigger': 39, 'variable': 52, 'builtInVariable': 5}
CONSTANTS = {
    'CONFIG - Enabled': 'false', 'CONFIG - Allowed Hostname': HOSTNAME,
    'CONFIG - GA4 Measurement ID': 'NOT_CONFIGURED',
    'META - Pixel ID': 'NOT_CONFIGURED', 'META - Enabled': 'false',
    'META - Consent Granted': 'false', 'MICROSOFT - UET ID': 'NOT_CONFIGURED',
    'MICROSOFT - Enabled': 'false', 'MICROSOFT - Consent Ready': 'false',
}
BUILTINS = {'PAGE_URL': 'Page URL', 'PAGE_HOSTNAME': 'Page Hostname',
            'PAGE_PATH': 'Page Path', 'REFERRER': 'Referrer', 'EVENT': 'Event'}
ADS_CONSENT = {'ad_storage', 'ad_user_data', 'ad_personalization'}
MACRO = re.compile(r'\{\{([^{}]+)\}\}')
BRAND = re.compile('sophos', re.I)
SENSITIVE = re.compile(
    r'\b(?:GTM-[A-Z0-9]+|G-[A-Z0-9]{5,})\b|'
    r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|'
    r'https?://|www\.|(?:/(?:Users|home|private|var|tmp)/)|'
    r'(?<!\d)\d{7,}(?!\d)', re.I)
DOMAIN = re.compile(r'(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}', re.I)
PRIVATE_METADATA_KEYS = {'accountId', 'containerId', 'containerVersionId', 'workspaceId',
                         'fingerprint', 'path', 'tagManagerUrl', 'publicId', 'tagIds',
                         'exportTime', 'notes'}
BASE_PARAMETERS = {
    'c_navTimingApi': 'false', 'tagId': '{{MICROSOFT - UET ID}}',
    'c_consentInheritGtm': 'true', 'c_storeConvTrackCookies': 'true',
    'uetqName': 'marketing_uetq', 'c_removeQueryFromUrls': 'false',
    'c_disableAutoPageView': 'false', 'c_enhancedConversion': 'false',
    'c_consentUpdates': 'true', 'eventType': 'PAGE_LOAD', 'c_enableAutoSpaTracking': 'false',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def params(row):
    rows = row.get('parameter', [])
    out = {item['key']: item.get('value') for item in rows}
    require(len(out) == len(rows), 'Duplicate parameter key')
    return out


def index(rows):
    out = {row['name']: row for row in rows}
    require(len(out) == len(rows), 'Duplicate entity name')
    return out


def walk(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path + ('<key>', key), key
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for offset, child in enumerate(value):
            yield from walk(child, path + (offset,))
    else:
        yield path, value


def privacy_check(document):
    header_path = ('containerVersion', 'container', 'name')
    brand_paths = []
    for path, value in walk(document):
        if len(path) >= 2 and path[-2] == '<key>':
            require(value not in PRIVATE_METADATA_KEYS, 'Private native metadata key detected')
        if isinstance(value, int) and not isinstance(value, bool):
            require(abs(value) < 1000000, 'Unexpected large numeric scalar')
        if not isinstance(value, str):
            continue
        if BRAND.search(value):
            brand_paths.append(path)
            require(path == header_path and value == CONTAINER_NAME,
                    'Brand token outside the authorized container name')
        require(not SENSITIVE.search(value), 'Private identifier, contact, URL, or path detected')
        if DOMAIN.fullmatch(value):
            require(value == HOSTNAME or re.fullmatch(
                r'(?:measurement\.parameters|eventModel)\.[a-z_][a-z0-9_]*', value),
                'Non-placeholder hostname-like value detected')
    require(brand_paths == [header_path], 'Container brand exception is missing or duplicated')


def consent(tag, expected):
    actual = tag['consentSettings']
    require(set(actual) == {'consentStatus', 'consentType'} and
            actual['consentStatus'] == 'NEEDED' and
            set(actual['consentType']) == {'type', 'list'} and
            actual['consentType']['type'] == 'LIST' and
            len(actual['consentType']['list']) == len(expected) and
            all(set(item) == {'type', 'value'} and item['type'] == 'TEMPLATE'
                for item in actual['consentType']['list']) and
            {item['value'] for item in actual['consentType']['list']} == expected,
            'Required native additional-consent settings changed')


def equals(left, right, negate=False, regex=False):
    result = {'type': 'MATCH_REGEX' if regex else 'EQUALS', 'parameter': [
        {'type': 'TEMPLATE', 'key': 'arg0', 'value': left},
        {'type': 'TEMPLATE', 'key': 'arg1', 'value': right}]}
    if negate:
        result['parameter'].append({'type': 'BOOLEAN', 'key': 'negate', 'value': 'true'})
    return result


def meta_html(event):
    return ("<script>\n(function () {\n"
            "  var enabled = '{{META - Enabled}}';\n"
            "  var pixelId = '{{META - Pixel ID}}';\n"
            "  var metaConsent = '{{META - Consent Granted}}';\n"
            "  if (enabled !== 'true' || metaConsent !== 'true' || !/^[0-9]{5,25}$/.test(pixelId)) return;\n"
            "  if (typeof window.fbq !== 'function') return;\n"
            "  window.fbq('trackSingle', pixelId, '" + event + "', {});\n"
            "}());\n</script>\n")


def audit(document):
    require(set(document) == {'exportFormatVersion', 'containerVersion'} and
            document['exportFormatVersion'] == 2, 'Unexpected portable export envelope')
    version = document['containerVersion']
    require(set(version) == {'container', *FAMILIES}, 'Unexpected version metadata or entity family')
    require(version['container'] == {'name': CONTAINER_NAME, 'usageContext': ['WEB']},
            'Portable container header must contain only its generic name and WEB context')
    require({family: len(version[family]) for family in FAMILIES} == COUNTS, 'Unexpected component counts')
    privacy_check(document)
    entities = {}
    all_ids = set()
    for family in FAMILIES:
        entities[family] = index(version[family])
        for row in version[family]:
            require(set(row) <= ENTITY_KEYS[family], 'Unexpected native metadata or entity field')
            if family in IDS:
                value = row[IDS[family]]
                require(isinstance(value, str) and value.isdecimal() and
                        0 < int(value) < 1000000 and value not in all_ids,
                        'Unsafe or colliding local entity ID')
                all_ids.add(value)
    tags, triggers, variables = (entities[family] for family in ('tag', 'trigger', 'variable'))
    require(Counter(row['type'] for row in tags.values()) == {'gaawe': 33, 'html': 2, 'baut': 3},
            'Unsupported tag family or extra sender')
    require(Counter(row['type'] for row in variables.values()) == {'v': 42, 'c': 9, 'smm': 1},
            'Unexpected variable types')
    require({row['type']: row['name'] for row in version['builtInVariable']} == BUILTINS,
            'Built-in variable set changed')
    trigger_ids = {row['triggerId']: row['name'] for row in triggers.values()}
    available = set(variables) | set(entities['builtInVariable']) | {'_event'}
    for _, value in walk(version):
        if isinstance(value, str):
            require(set(MACRO.findall(value)) <= available, 'Unresolved variable macro')
    for tag in tags.values():
        require(tag.get('paused') is True, 'Every public tag must remain paused')
        require(tag.get('monitoringMetadata') == {'type': 'MAP'}, 'Unexpected monitoring payload')
        for field in ('firingTriggerId', 'blockingTriggerId'):
            refs = tag.get(field, [])
            require(len(refs) == len(set(refs)) and set(refs) <= set(trigger_ids),
                    'Duplicate or unresolved trigger reference')
    constants = {name: params(row).get('value') for name, row in variables.items() if row['type'] == 'c'}
    require(constants == CONSTANTS, 'A destination ID or inactive configuration constant changed')
    for row in variables.values():
        require(row.get('formatValue', {}) == {}, 'Unexpected variable formatting payload')
        if row['type'] == 'c':
            require(row['parameter'] == [{'type': 'TEMPLATE', 'key': 'value',
                                         'value': CONSTANTS[row['name']]}],
                    'Unexpected configuration constant payload')
    lookup = [row for row in variables.values() if row['type'] == 'smm'][0]
    require(lookup['name'] == 'LOOKUP - Dealer GA4 Measurement ID', 'Unexpected lookup variable')
    lookup_params = {row['key']: row for row in lookup['parameter']}
    require(set(lookup_params) == {'setDefaultValue', 'input', 'defaultValue', 'map'} and
            lookup_params['setDefaultValue']['value'] == 'true' and
            lookup_params['input']['value'] == '{{Page Hostname}}' and
            lookup_params['defaultValue']['value'] == 'NOT_CONFIGURED' and
            lookup_params['map'] == {'type': 'LIST', 'key': 'map', 'list': [
                {'type': 'MAP', 'map': [
                    {'type': 'TEMPLATE', 'key': 'key', 'value': ''},
                    {'type': 'TEMPLATE', 'key': 'value', 'value': 'NOT_CONFIGURED'}]}]},
            'Lookup must contain only the single empty-hostname placeholder row')
    for row in variables.values():
        if row['type'] == 'v':
            values = params(row)
            require(set(values) == {'dataLayerVersion', 'setDefaultValue', 'name'} and
                    values['dataLayerVersion'] == '2' and values['setDefaultValue'] == 'false' and
                    re.fullmatch(r'(?:measurement\.parameters|eventModel)\.[a-z_][a-z0-9_]*', values['name']),
                    'Unexpected data-layer path or default value')
    normalized = {name: row for name, row in triggers.items() if name.startswith('CE - ')}
    require(len(normalized) == 33, 'Unexpected normalized trigger inventory')
    global_gates = [equals('{{Page Hostname}}', '{{CONFIG - Allowed Hostname}}'),
                    equals('{{CONFIG - Enabled}}', 'true')]
    for name, row in normalized.items():
        require(row['type'] == 'CUSTOM_EVENT' and row['customEventFilter'] == [
            equals('{{_event}}', 'measurement__' + name.removeprefix('CE - '))] and
            row['filter'] == global_gates, 'Normalized source contract or global gates changed')
    di = {name: row for name, row in triggers.items() if name.startswith('DI - CE - ')}
    require(len(di) == 2, 'Unexpected provider-observation trigger inventory')
    for name, row in di.items():
        require(row['customEventFilter'] == [equals('{{_event}}', name.removeprefix('DI - CE - '))] and
                row['filter'] == [equals('{{Page Hostname}}', HOSTNAME),
                                  equals('{{DI - DLV - event_owner}}', 'dealer inspire')],
                'Provider-observation hostname or event contract changed')
    for tag in tags.values():
        firing = [trigger_ids[value] for value in tag.get('firingTriggerId', [])]
        require(not set(firing) & set(di), 'Provider-observation triggers must remain unattached')
        if tag['type'] == 'gaawe':
            values = params(tag)
            require(tag['name'] == 'ASC - ' + values['eventName'] and
                    firing == ['CE - ' + values['eventName']] and
                    values['measurementIdOverride'] == '{{CONFIG - GA4 Measurement ID}}' and
                    values['sendEcommerceData'] == 'false' and
                    tag['tagFiringOption'] == 'ONCE_PER_EVENT', 'GA4 event sender contract changed')
            require(set(values) == {'sendEcommerceData', 'eventSettingsTable', 'eventName',
                                    'measurementIdOverride'}, 'Unexpected GA4 sender parameter')
            table = next(item for item in tag['parameter'] if item['key'] == 'eventSettingsTable')
            require(table['type'] == 'LIST', 'Unexpected GA4 event settings table type')
            for entry in table['list']:
                require(entry['type'] == 'MAP' and len(entry['map']) == 2,
                        'Unexpected GA4 event parameter schema')
                fields = {item['key']: item.get('value') for item in entry['map']}
                require(set(fields) == {'parameter', 'parameterValue'} and
                        re.fullmatch(r'[a-z][a-z0-9_]*', fields['parameter']) and
                        fields['parameterValue'] == '{{DLV - ' + fields['parameter'] + '}}',
                        'GA4 event parameter must use its declared generic data-layer variable')
            consent(tag, {'analytics_storage'})
    signals = {'successful_inquiry': ('asc_form_submission', 'Lead'),
               'phone_link_click': ('asc_click_to_call', 'Contact')}
    for signal, (source_event, meta_event) in signals.items():
        tag = tags['META - ' + signal]
        require(tag['type'] == 'html' and params(tag) == {
            'html': meta_html(meta_event), 'supportDocumentWrite': 'false'} and
            [trigger_ids[value] for value in tag['firingTriggerId']] == ['CE - ' + source_event] and
            not tag.get('blockingTriggerId') and tag['tagFiringOption'] == 'ONCE_PER_EVENT',
            'Meta must remain the reviewed existing-Pixel event-only implementation')
        consent(tag, ADS_CONSENT)
    base = tags['MICROSOFT - Page View']
    require(params(base) == BASE_PARAMETERS and base['tagFiringOption'] == 'ONCE_PER_LOAD' and
            [trigger_ids[value] for value in base['firingTriggerId']] == ['MICROSOFT - Page View'],
            'Native UET base configuration changed')
    id_regex = '^[1-9][0-9]{0,18}$'
    require(triggers['MICROSOFT - Page View']['type'] == 'PAGEVIEW' and
            triggers['MICROSOFT - Page View']['filter'] == global_gates + [
                equals('{{MICROSOFT - Enabled}}', 'true'),
                equals('{{MICROSOFT - Consent Ready}}', 'true'),
                equals('{{MICROSOFT - UET ID}}', id_regex, regex=True)],
            'Native UET PageView gates changed')
    blocks = {'MICROSOFT - BLOCK - Disabled': equals('{{MICROSOFT - Enabled}}', 'true', negate=True),
              'MICROSOFT - BLOCK - Consent Not Ready': equals('{{MICROSOFT - Consent Ready}}', 'true', negate=True),
              'MICROSOFT - BLOCK - Invalid UET ID': equals('{{MICROSOFT - UET ID}}', id_regex, negate=True, regex=True)}
    for name, condition in blocks.items():
        require(triggers[name]['type'] == 'CUSTOM_EVENT' and
                triggers[name]['customEventFilter'] == [equals('{{_event}}', '.*', regex=True)] and
                triggers[name]['filter'] == [condition], 'Native UET fail-closed exception changed')
    for name, tag in tags.items():
        if tag['type'] != 'baut':
            continue
        consent(tag, ADS_CONSENT)
        require({trigger_ids[value] for value in tag.get('blockingTriggerId', [])} == set(blocks),
                'Every UET tag needs all three independent blocking exceptions')
        if name != 'MICROSOFT - Page View':
            signal = name.removeprefix('MICROSOFT - ')
            require(signal in signals and params(tag) == {'uetqName': 'marketing_uetq',
                    'customEventAction': signal, 'eventType': 'CUSTOM'} and
                    tag['tagFiringOption'] == 'ONCE_PER_EVENT' and
                    [trigger_ids[value] for value in tag['firingTriggerId']] == ['CE - ' + signals[signal][0]],
                    'Native UET custom-event configuration changed')
    return {'result': 'PASS_PUBLIC_INACTIVE_PORTABLE_EXPORT', 'counts': COUNTS,
            'all_tags_paused': True, 'customer_lookup_rows': 0,
            'empty_hostname_placeholder_rows': 1, 'native_ownership_metadata': False,
            'destination_ids_configured': False, 'reference_closure': True,
            'native_import_compatibility': 'NOT_CHECKED_BY_STATIC_AUDITOR'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', nargs='?', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'containers/automotive.json')
    args = parser.parse_args()
    report = audit(json.loads(args.export.read_text()))
    report['sha256'] = hashlib.sha256(args.export.read_bytes()).hexdigest()
    manifest_path = Path(__file__).resolve().parents[1] / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        require(len(manifest['templates']) == 1 and
                manifest['templates'][0]['file'] == 'containers/automotive.json' and
                manifest['templates'][0]['sha256'] == report['sha256'],
                'Export differs from the public bundle manifest')
        report['bundle_manifest_hash_matches'] = True
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
