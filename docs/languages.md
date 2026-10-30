# Source languages

Source analysis and output language are independent: `--language auto|rust|python|dart`
selects parsers; `--output-language zh|en` selects the interface and explanations.
`auto` is the default and indexes registered suffixes. An explicit source language
narrows work to that language. Ambiguous symbols still require `--file` or a full ID.
Python/Dart qualified method selectors accept both `Worker::run` and `Worker.run`.

| Language | Parser and facts | Conservative call hints |
| --- | --- | --- |
| Rust | Pinned ast-grep; functions, impls, types, branches, `?`, returns, error constructors, macros | Existing self/annotated parameter/path candidates; macros remain unexpanded |
| Python (`.py`, `.pyi`) | Standard-library AST; sync/async/nested functions, class methods, signatures, if/loops/match, try/except/else/finally, await, return/raise/assert, class shape | Lexical functions, explicit local imports/aliases, bound receivers and plain annotated parameter types |
| Dart (`.dart`) | Same pinned ast-grep; top-level/local functions, methods, constructors, getters/setters, arrow/async bodies, conditions/switch/loops, try/on/catch/finally, await, return/throw/rethrow, class/type shape | Local library members, explicit relative imports/prefixes, this and plain annotated parameter types |

Python parsing accepts syntax supported by the Python interpreter running the Kit.
No target module is imported and no reviewed code is executed. Dart extraction does
not require Dart or Flutter SDKs; it is not the SDK analyzer. Both preserve unknown
receivers and callable/rebound names rather than expanding an unrelated same-name
method. Class evidence uses declarations and field/signature shape, so an unrelated
method-body change does not alone stale every method in that class.

This remains syntax analysis. Python decorators, monkey patching, wildcard imports,
custom package roots and runtime imports; Dart package/export/conditional-import
resolution, named `part of` libraries, inheritance, extensions, dynamic dispatch,
generated bindings and SDK types are not fully resolved. Implicit exceptions are not
enumerated. Anonymous callback bodies are not attributed to their enclosing function
or automatically expanded. Class constructors/callable objects and operators may
remain unresolved. A unique candidate is not proof of runtime dispatch.

## Mixed business flows

Use one common repository root and relative `file + symbol` references. A node may
cite several languages. With `--language auto`, the same facts, evidence hashing,
staleness checks, byte-budget packets and HTML template apply to every source.
Per-file and per-adapter-version caches are separate from single-language caches.

Success/resume edges are explicitly authored business handoffs. They do not imply
that a Dart function actually invokes Python or Rust. Calls within a function only
search candidates in its own language; FFI/RPC bridges must be cited and explained
explicitly. Syntax errors in selected indexed sources are rejected even when a
line-range reference is used. Unsupported files remain source context only.

The fictional mixed example includes Dart input validation, optional Python ASCII
normalization with raw-text fallback, and a Rust UTF-8 byte-size gate. It deliberately
contains no cross-language runtime bridge. Generate its Chinese or English cards
using the corresponding explanations file, or run each function independently.

```sh
code-review business --manifest examples/document-pipeline/mixed-business.json --language auto --explanations examples/document-pipeline/mixed-explanations.zh.json --out out/mixed --depth 0
code-review business --manifest examples/document-pipeline/mixed-business.json --language auto --explanations examples/document-pipeline/mixed-explanations.en.json --output-language en --out out/mixed-en --depth 0
```
