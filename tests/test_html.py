from koyoapp.html import (
    Element,
    Markup,
    body,
    button,
    div,
    h1,
    html,
    img,
    input,
    label,
    p,
    path,
    raw,
    render_html,
    span,
    svg,
)


def test_single_text_child():
    assert str(div()["hi"]) == "<div>hi</div>"


def test_empty_div():
    assert str(div()) == "<div></div>"


def test_class_passes_through():
    assert str(div(class_="p-4 rounded")) == '<div class="p-4 rounded"></div>'


def test_text_is_escaped():
    assert str(p()["<b>&"]) == "<p>&lt;b&gt;&amp;</p>"


def test_attribute_value_is_escaped():
    assert str(div(title='say "hi"')) == '<div title="say &quot;hi&quot;"></div>'


def test_void_element():
    assert str(img(src="/logo.png")) == '<img src="/logo.png">'


def test_boolean_attributes():
    assert str(input(disabled=True, hidden=False, required=True)) == "<input disabled required>"


def test_nested_children():
    assert str(div()[span()["a"], p()["b"]]) == "<div><span>a</span><p>b</p></div>"


def test_list_child_is_flattened():
    assert str(div()["a", ["b", "c"]]) == "<div>abc</div>"


def test_generator_child():
    parts = div()[[h1()[item] for item in ("one", "two")]]
    assert str(parts) == "<div><h1>one</h1><h1>two</h1></div>"


def test_none_children_are_ignored():
    assert str(div()[None, "a", None]) == "<div>a</div>"


def test_raw_markup():
    assert str(div()[Markup("<b>x</b>")]) == "<div><b>x</b></div>"
    assert str(div()[raw("<i>y</i>")]) == "<div><i>y</i></div>"


def test_render_html_adds_doctype_for_html_root():
    page = html()[body()["x"]]
    assert render_html(page) == "<!doctype html>\n<html><body>x</body></html>"


def test_render_html_without_html_root():
    assert render_html(div()["x"]) == "<div>x</div>"


def test_integer_attributes():
    assert str(img(width=400)) == '<img width="400">'


def test_htmx_attributes_are_hyphenated():
    button_html = str(button(hx_post="/like", hx_target="#like-count", hx_swap="outerHTML"))
    assert button_html == '<button hx-post="/like" hx-target="#like-count" hx-swap="outerHTML"></button>'


def test_data_and_aria_attributes_are_hyphenated():
    assert str(div(data_theme="dark", aria_label="close")) == (
        '<div data-theme="dark" aria-label="close"></div>'
    )


def test_factories_return_elements():
    assert isinstance(div, type(lambda: None))
    assert isinstance(div()["x"], Element)


def test_positional_text_children():
    assert str(div("a", "b")) == "<div>ab</div>"


def test_positional_element_children():
    assert str(div(span()["a"], p()["b"])) == "<div><span>a</span><p>b</p></div>"


def test_positional_list_child_flattens():
    items = [span()["a"], span()["b"]]
    assert str(div(items, class_="row")) == '<div class="row"><span>a</span><span>b</span></div>'


def test_positional_children_with_attributes():
    assert str(label("Name", class_="bold")) == '<label class="bold">Name</label>'
    assert str(h1(span("Creative "), span("Developer", **{"class": "text-gradient"}), **{"class": "title"})) == (
        '<h1 class="title"><span>Creative </span><span class="text-gradient">Developer</span></h1>'
    )


def test_body_positional_python_keyword_shadowing():
    out = str(body(**{"class": "bg-surface-900"}))
    assert out == '<body class="bg-surface-900"></body>'


def test_icon_builder_pattern():
    icon = svg(fill="none", viewBox="0 0 24 24", **{"class": "w-5 h-5"})[
        path(d="M6 12 3.269 3.126")
    ]
    out = str(button(span("Send Message", **{"class": "relative z-10"}), span(icon), **{"class": "btn"}))
    assert out == (
        '<button class="btn"><span class="relative z-10">Send Message</span>'
        '<span><svg fill="none" viewBox="0 0 24 24" class="w-5 h-5"><path d="M6 12 3.269 3.126"></path></svg></span></button>'
    )


def test_cls_alias_maps_to_class():
    assert str(div("x", cls="p-2")) == '<div class="p-2">x</div>'


def test_bracket_style_still_works_after_positional_support():
    assert str(div(class_="card")["a", ["b", "c"]]) == '<div class="card">abc</div>'