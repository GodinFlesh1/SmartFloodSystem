import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = "http://localhost:8000";

  static Future<List<dynamic>> getNearbyStations(
      double lat, double lon) async {

    final uri = Uri.parse("$baseUrl/api/stations/nearby").replace(
        queryParameters: {
          "lat": lat.toString(),
          "lon": lon.toString(),
          "radius_km": "10"
        },
    );

    final response = await http.get(uri);


    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      print("Hello, stations loaded!");
      return data["stations"];
    } else {
      throw Exception("Failed to load stations");
    }
  }
}