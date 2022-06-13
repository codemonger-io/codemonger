// Expands any URI not ending with `/index.html` with `/index.html`.
function handler(event) {
  return handlerImpl(event);
}

// Implementation of `handler`.
// `handler` just calls `handlerImpl`.
//
// The reason why this separation is necessary is that `babel-plugin-rewire`
// cannot obtain a function that is not used in this source file; i.e.,
// `babel-plugin-rewire` cannot obtain `handler` that is called from the
// outside.
// `babel-plugin-rewire` is introduced to test functions in this source file.
// We cannot export functions from this source file because the CloudFront
// Functions runtime does not like the `module.exports` idiom.
//
// Reference:
// https://www.uglydirtylittlestrawberry.co.uk/posts/unit-testing-cloudfront-functions/
function handlerImpl(event) {
  var request = event.request;
  // 1. A URI is given → `uri`.
  var uri = request.uri;
  // 2. Locate a first optional hash (`#`) in `uri` and separate a fragment (substring starting from `#` or empty) from it → [`uri`, `fragment`].
  var parts = splitStringByFirst(uri, '#');
  uri = parts[0];
  var fragment = parts[1];
  // 3. Locate a first optional question mark (`?`) in `uri` and separate a query (substring starting from `?` or empty) from it → [`uri`, `query`].
  parts = splitStringByFirst(uri, '?');
  uri = parts[0];
  var query = parts[1];
  // 4. Locate the last slash (`/`) in `uri` and separate the last path segment (substring starting from `/`) from it → [`uri`, `last path segment`].
  parts = splitStringByLast(uri, '/');
  uri = parts[0];
  var lastSegment = parts[1];
  // 5. If `last path segment` contains no dots (`.`), expand `last path segment` with,
  //    - `"index.html"` if `last path segment` ends with `/`,
  //    - `"/index.html"` otherwise
  if (lastSegment.indexOf('.') === -1) {
    if (lastSegment.endsWith('/')) {
      lastSegment += 'index.html';
    } else {
      lastSegment += '/index.html';
    }
  }
  // 6. Return a new URI = `uri` + `last path segment` + `query` + `fragment`
  request.uri = uri + lastSegment + query + fragment;
  return request;
}

// Splits a given string at the first occurrence of a given delimiter.
//
// Returns an array of two elements.
// 1. the first item is a substring of `str` until the first occurrence of
//    `delimiter` not including `delimiter` itself.
// 2. the second item is a substring of `str` from the first occurrence of
//    `delimiter` including `delimiter` itself.
//
// If there is no `delimiter` in `str`, the first item is `str` itself, and the
// second item is an empty string.
function splitStringByFirst(str, delimiter) {
  return splitStringAt(str, str.indexOf(delimiter));
}

// Splits a given string at the last occurrence of a given delimiter.
//
// Returns an array of two elements,
// 1. the first item is a substring of `str` until the last occurrence of
//    `delimiter` not including `delimiter` itself.
// 2. the second item is a substring of `str` from the last occurrence of
//    `delimiter` including `delimiter` itself.
//
// If there is no `delimiter` in `str`, the first item is `str` itself, and the
// second item is an empty string.
function splitStringByLast(str, delimiter) {
  return splitStringAt(str, str.lastIndexOf(delimiter));
}

// Splits a given string at the index located by a given function.
//
// Returns an array of two elements.
// 1. the first item is a substring of `str` until `index` (exclusive)
// 2. the second item is a substring of `str` from `index` (exclusive)
//
// If `index` is `-1`, the first item is `str` itself, and the second item is
// an empty string.
function splitStringAt(str, index) {
  if (index !== -1) {
    return [
      str.slice(0, index),
      str.slice(index),
    ];
  } else {
    return [str, ''];
  }
}
