import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {

  List stations = [];
  bool loading = true;
  String locationStatus = "Detecting location...";
  String floodStatus = "Unknown";

  @override
  void initState() {
    super.initState();
    loadStations();
  }

  Future<Position> getLocation() async {

    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      setState(() {
        locationStatus = "Location services disabled";
      });
      throw Exception("Location services disabled");
    }

    LocationPermission permission = await Geolocator.checkPermission();

    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    Position position = await Geolocator.getCurrentPosition();

    setState(() {
      locationStatus =
      "Lat: ${position.latitude.toStringAsFixed(3)}, Lon: ${position.longitude.toStringAsFixed(3)}";
    });

    return position;
  }

  Future<void> loadStations() async {

    setState(() {
      loading = true;
    });

    try {

      final position = await getLocation();

      final data = await ApiService.getNearbyStations(
        position.latitude,
        position.longitude,
      );

      setState(() {
        stations = data;
        loading = false;
      });

      if (stations.isNotEmpty) {
        final level = stations[0]["latest_reading"]?["water_level"];
        floodStatus = predictFlood(level);
      }

    } catch (e) {

      setState(() {
        loading = false;
        floodStatus = "No data available";
      });

      print(e);
    }
  }

  String predictFlood(double? level) {

    if (level == null) return "No Data";

    if (level > 3) return "High Flood Risk";
    if (level > 2) return "Medium Risk";
    if (level > 1) return "Low Risk";

    return "Safe";
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(
      appBar: AppBar(
        title: const Text("EcoFlood Monitor"),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            /// Location Section
            Card(
              child: ListTile(
                leading: const Icon(Icons.location_on),
                title: const Text("Your Location"),
                subtitle: Text(locationStatus),
              ),
            ),

            const SizedBox(height: 10),

            /// Flood Status
            Card(
              child: ListTile(
                leading: const Icon(Icons.warning),
                title: const Text("Flood Risk"),
                subtitle: Text(floodStatus),
              ),
            ),

            const SizedBox(height: 20),

            const Text(
              "Nearby Stations",
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 10),

            /// Station List
            Expanded(
              child: loading
                  ? const Center(child: CircularProgressIndicator())
                  : stations.isEmpty
                  ? const Center(
                child: Text("No nearby stations available"),
              )
                  : ListView.builder(
                itemCount: stations.length,
                itemBuilder: (context, index) {

                  final station = stations[index];
                  final level =
                  station["latest_reading"]?["water_level"];

                  return Card(
                    child: ListTile(
                      title: Text(station["station_name"]),
                      subtitle: Text(
                          "River: ${station["river_name"] ?? "Unknown"}"),
                      trailing: Text("Level: ${level ?? "N/A"}"),
                    ),
                  );
                },
              ),
            ),

            /// Refresh Button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: loadStations,
                child: const Text("Refresh Data"),
              ),
            )
          ],
        ),
      ),
    );
  }
}