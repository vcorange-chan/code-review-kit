// Fictional request preparation; no network or language bridge is implemented.
String prepareRequest(String value) {
  final trimmed = value.trim();
  if (trimmed.isEmpty) {
    throw ArgumentError('empty request');
  }
  return trimmed;
}
