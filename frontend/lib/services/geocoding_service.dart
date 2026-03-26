import 'dart:convert';
import 'package:http/http.dart' as http;

class CountryResult {
  final String countryName;
  final String countryCode; // ISO 3166-1 alpha-2, e.g. "gb", "us"

  CountryResult({required this.countryName, required this.countryCode});

  bool get isUK => countryCode.toLowerCase() == 'gb';
}

class GeocodingService {
  /// Reverse geocodes [lat]/[lon] using OpenStreetMap Nominatim.
  /// Returns null if the country cannot be determined.
  Future<CountryResult?> getCountry(double lat, double lon) async {
    final uri = Uri.parse(
      'https://nominatim.openstreetmap.org/reverse?lat=$lat&lon=$lon&format=json',
    );

    final response = await http.get(
      uri,
      headers: {'Accept-Language': 'en', 'User-Agent': 'EcoFloodApp/1.0'},
    ).timeout(const Duration(seconds: 10));

    if (response.statusCode != 200) return null;

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final address = data['address'] as Map<String, dynamic>?;
    if (address == null) return null;

    final countryName = address['country'] as String? ?? 'Unknown';
    final countryCode = address['country_code'] as String? ?? '';

    return CountryResult(countryName: countryName, countryCode: countryCode);
  }
}
