+++
title = "Introducing Zola"
date = 2022-06-13
updated = 2022-06-20
draft = false
+++

This website is generated with [Zola](https://www.getzola.org).
This blog post introduces my findings in using Zola.

<!-- more -->

## What is Zola?

[Zola](https://www.getzola.org) is a static site generator like [Hugo](https://gohugo.io).
It is written in [Rust](https://www.rust-lang.org).
Please refer to the [official documentation](https://www.getzola.org/documentation/getting-started/overview/) for more details.
I am neither the author nor a contributor of Zola by the way.

## Why did I choose Zola for my website?

I was attracted to Zola because its implementation language Rust was the language I was and am learning (as of June 13, 2022).
As long as I just use Zola the implementation language does not matter though.

## Using Bulma with Zola

[Bulma](https://bulma.io) is my favorite CSS framework and I wanted to apply it to this website.
I needed some tweaks before Bulma worked.

### Importing Bulma

Just throwing Bulma's `sass` folder and `bulma.sass` file into Zola's `sass` folder did not work, because Bulma exposes all the Sass files in the subfolders.
I found a [discussion about the same issue](https://github.com/getzola/zola/issues/431), and I decided to follow the solution suggested by the author of the issue.
Thus, I prefixed all the Bulma's sass files with an underscore (`_`) and it worked.

### Styling markdown with Bulma

To apply Bulma's styles to markdown contents rendered by Zola, I wrapped them in an element with the [`.content` class](https://bulma.io/documentation/elements/content/).
I found a [forum post about the same issue](https://zola.discourse.group/t/how-to-style-html-generated-from-markdown/868).

## Multilingual support

As I want to provide articles both in English and Japanese (日本語) from this website, multilingual support is crucial for me.
Zola supports [multilingual sites](https://www.getzola.org/documentation/content/multilingual/) though, that feature is not well-documented.

### Section _index.{code}.md file

A section is accompanied by a `_index.md` file.
If you want to write a section in a language other than the default one, you have to also create a `_index.{code}.md` file replacing `{code}` with the code of the language you want to use.
In my case, I prepared the following two files in each section,
- `_index.md` &rightarrow; English (default)
- `_index.ja.md` &rightarrow; Japanese

### Obtaining a section in a language-aware manner

You can use the [`get_section`](https://www.getzola.org/documentation/templates/overview/#get-section) function to obtain a section object at a specific path.
As `get_section` does not take any language option, it is a little tricky to request a section object in the current language given by the `lang` variable.
Simply concatenating `lang` like `"_index." ~ lang ~ ".md"` did not work, because it produced a wrong path for the default language like `_index.en.md` despite `_index.md` was expected.

So I made a macro `lang_ext` that is substituted with an appropriate extension for the current language.
It turns into `".{code}"` but an empty string for the default language.

```
{% macro lang_ext() %}{% if lang != config.default_language %}.{{ lang }}{% else %}{% endif %}{% endmacro lang_ext %}
```

I am using this macro like the following,

```
{% set lang_ext = macros::lang_ext() %}
{% set root = get_section(path="_index" ~ lang_ext ~ ".md") %}
```

You cannot do like `{% set root = get_section(path="_index" ~ macros::lang_ext() ~ ".md") %}` by the way.

### Obtaining the root URL of the current language

The root URL for a specific language is given as `{base_url}/{code}` except the one for the default language is given as `{base_url}`.
Like [_Obtaining a section in a specific language_](#Obtaining_a_section_in_a_language-aware_manner), the root URL for a specific language is also a little tricky.

Again I made a macro `lang_seg` that is substituted with an appropriate path segment for the current language.
It turns into `"/{code}"` but an empty string for the default language.

```
{% macro lang_seg() %}{% if lang != config.default_language %}/{{ lang }}{% else %}{% endif %}{% endmacro lang_seg %}
```

I am using this macro like the following,

```html
<a class="navbar-item" href="{{ config.base_url }}{{ macros::lang_seg() }}">
  <img src="/codemonger.svg" width="112" height="28" alt="codemonger logo">
</a>
```

### Switching the language of the current page

I wanted every page on my website to have a link to switch languages between English and Japanese, and I did not like to manually embed a link on every page.
So I decided to embed the link in `base.html` which is extended by every HTML template on this website.

The [`get_url`](https://www.getzola.org/documentation/templates/overview/#get-url) function looked suitable for this feature because it takes a `lang` option in addition to a `path` argument.
If I can obtain the path of the current page in the form of `@/{section}/{page}.md`, I can easily exchange it with the URL of the translation in a desired language through `get_url`.

After some trial and error, I realized that I can use `page.components` and `section.components` to form a `path` argument for `get_url`.
I carefully observed the behavior of `page.components` and `section.components`, and found,
- `page.components` and `section.components` are an array of path segments in the current path separated by a slash (`/`).
- `page.components` and `section.components` start with a language code unless the current language is the default one.
  The default language code is omitted.
- The last item of `page.components` is the name of the current page without an extension (`.md`).
- The last item of `section.components` is not an index, `_index.md`, but the name of the section.
- `section.components` of the root page of the default language is empty.

Then I came up with the following complicated template,

```
{% if page %}
{%   if lang == config.default_language %}
{%     set relative_path = page.components | join(sep="/") %}
{%   else %}
{%     set relative_path = page.components | slice(start=1) | join(sep="/") %}
{%   endif %}
{%   set internal_path = "@/" ~ relative_path ~ ".md" %}
{% elif section %}
{%   if section.components | length  > 0 %}
{%     if lang == config.default_language %}
{%       set relative_path = section.components | join(sep="/") %}
{%     else %}
{%       set relative_path = section.components | slice(start=1) | join(sep="/") %}
{%     endif %}
{%     set internal_path = "@/" ~ relative_path ~ "/_index.md" %}
{%   else %}
{%     set internal_path = "/" %}
{%   endif %}
{% endif %}
```

After the above template is evaluted, `get_url(path=internal_path, lang={code})` will give you the URL of the page in a language given by `{code}`.

A major drawback is that I have to prepare both English and Japanese translations for every single page, or Zola ends up with an error.

### Difficulties in anchor IDs

Zola turns every section title in markdown into a [slugified anchor ID](https://www.getzola.org/documentation/getting-started/configuration/#slugification-strategies) by default.
There is no problem as long as a section title contains only ASCII characters, but once non-ASCII characters, e.g., Japanese characters, are involved, Zola emits an unpredictable, at least for me, anchor ID.
For instance, a section title "言語を意識してセクションを取得する" turns into an anchor ID "yan-yu-woyi-shi-sitesekusiyonwoqu-de-suru".

This conversion can be avoided by changing the `slugify` option for anchors to `"safe"` in the `config.toml` file.
But this configuration introduces unfamiliar\* behavior over non-letter characters; e.g., whitespace is replaced with an underscore (`_`) not a dash (`-`), capital letters stay, and symbols also stay.
(\*I am familiar with GitHub rules.)

My workaround so far is to make the `slugify` option for anchors `"safe"` and accept the new rules.

I should suggest a pull request someday, maybe.

## Serving contents from S3 via CloudFront

I am serving this website from an [Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) bucket through an [Amazon CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html) distribution though, there were some challenges to doing so.
But this is not actually Zola's issue, I am going to leave it for [another post](/blog/0002-serving-contents-from-s3-via-cloudfront).