# =============================================================================
# Minet Apply Scraper Function
# =============================================================================
#
# Function taking a scraper definition and applying its logic recursively
# to yield its result.
#
import re
import json
import soupsieve
from urllib.parse import urljoin

from minet.utils import nested_get
from minet.scrape.constants import EXTRACTOR_NAMES

DEFAULT_CONTEXT = {}


def get_aliases(o, aliases):
    for alias in aliases:
        if alias in o:
            return o[alias]


def merge_contexts(global_context, local_context):
    if global_context is None:
        return local_context

    for k, v in global_context.items():
        if k not in local_context:
            local_context[k] = v

    return local_context


def extract(element, extractor_name):
    if extractor_name == 'text':
        return element.get_text().strip()

    if extractor_name == 'html' or extractor_name == 'inner_html':
        return element.decode_contents().strip()

    if extractor_name == 'outer_html':
        return str(element).strip()

    raise TypeError('Unknown "%s" extractor' % extractor_name)


EVAL_CONTEXT = {

    # Dependencies
    'json': json,
    'urljoin': urljoin,
    're': re,
}


# NOTE: this is not threadsafe, but it does not have to be
def eval_expression(expression, element=None, elements=None, value=None,
                    context=None, html=None, root=None):

    # Local variables
    EVAL_CONTEXT['element'] = element
    EVAL_CONTEXT['elements'] = elements
    EVAL_CONTEXT['value'] = value

    # Context
    EVAL_CONTEXT['context'] = context
    EVAL_CONTEXT['html'] = html
    EVAL_CONTEXT['root'] = root

    return eval(expression, None, EVAL_CONTEXT)


def tabulate(element, headers_inference='th', headers=None):
    body = element.find('tbody', recursive=False)
    head = element.find('thead', recursive=False)

    if body is None:
        body = element

    if head is None:
        head = element

    trs = body.select('tr:has(td)', recursive=False)
    ths = head.select('tr > th', recursive=False)

    if headers is None:
        if headers_inference == 'th':
            headers = [th.get_text() for th in ths]

    for tr in trs:
        yield {headers[i]: td.get_text() for i, td in enumerate(tr.find_all('td', recursive=False))}


def interpret_scraper(scraper, element, root=None, html=None, context=None):

    # Is this a tail call of item?
    if isinstance(scraper, str):
        if scraper in EXTRACTOR_NAMES:
            return extract(element, scraper)

        return element.get(scraper)

    sel = get_aliases(scraper, ['sel', '$'])
    iterator = get_aliases(scraper, ['iterator', 'it', '$$'])

    # First we need to solve local selection
    if sel is not None:
        element = soupsieve.select_one(sel, element)
    elif 'sel_eval' in scraper:

        # TODO: validate
        element = eval_expression(
            scraper['sel_eval'],
            element=element,
            elements=[],
            context=context,
            html=html,
            root=root
        )

    if element is None:
        return None

    # Then we need to solve iterator
    single_value = True

    if iterator is not None:
        elements = soupsieve.select(iterator, element)
        single_value = False
    elif 'iterator_eval' in scraper:
        elements = eval_expression(
            scraper['iterator_eval'],
            element=element,
            elements=[],
            context=context,
            html=html,
            root=root
        )
        single_value = False
    else:
        elements = [element]

    # Handling local context
    if 'set_context' in scraper:
        local_context = {}

        for k, field_scraper in scraper['set_context'].items():
            local_context[k] = interpret_scraper(
                field_scraper,
                element,
                root=root,
                html=html,
                context=context
            )

        context = merge_contexts(context, local_context)

    # Actual iteration
    acc = None if single_value else []

    already_seen = set() if 'uniq' in scraper and not single_value else None

    for element in elements:
        value = None

        # Do we have fields?
        if 'fields' in scraper:
            value = {}

            for k, field_scraper in scraper['fields'].items():
                value[k] = interpret_scraper(
                    field_scraper,
                    element,
                    root=root,
                    html=html,
                    context=context
                )

        # Do we have a scalar?
        elif 'item' in scraper:

            # Default value is text
            value = interpret_scraper(
                scraper['item'],
                element,
                root=root,
                html=html,
                context=context
            )

        else:

            if 'attr' in scraper:
                value = element.get(scraper['attr'])
            elif 'extract' in scraper:
                value = extract(element, scraper['extract'])
            elif 'get_context' in scraper:
                value = nested_get(scraper['get_context'], context)
            elif 'default' in scraper:
                value = scraper['default']
            else:

                # Default value is text
                value = extract(element, 'text')

            # Eval?
            if 'eval' in scraper:
                value = eval_expression(
                    scraper['eval'],
                    element=element,
                    elements=elements,
                    value=value,
                    context=context,
                    html=html,
                    root=root
                )

        # Default value after all?
        if 'default' in scraper and value is None:
            value = scraper['default']

        if single_value:
            acc = value
        else:

            # Filtering?
            if 'filter_eval' in scraper:
                passed_filter = eval_expression(
                    scraper['filter_eval'],
                    element=element,
                    elements=elements,
                    value=value,
                    context=context,
                    html=html,
                    root=root
                )

                if not passed_filter:
                    continue

            if 'filter' in scraper:
                filtering_clause = scraper['filter']

                if filtering_clause is True and not value:
                    continue

                if isinstance(filtering_clause, str) and not value.get(filtering_clause):
                    continue

            if 'uniq' in scraper:
                uniq_clause = scraper['uniq']
                k = value

                if uniq_clause is True and value in already_seen:
                    continue

                if isinstance(uniq_clause, str):
                    k = value.get(uniq_clause)

                    if k in already_seen:
                        continue

                already_seen.add(k)

            acc.append(value)

    return acc
