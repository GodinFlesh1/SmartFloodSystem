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

  @override
  void initState() {
    super.initState();
    loadStations();
  }

  Future<Position> getLocation() async {

    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception("Location services disabled");
    }

    LocationPermission permission = await Geolocator.checkPermission();

    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    return await Geolocator.getCurrentPosition();
  }

  Future<void> loadStations() async {

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

    } catch (e) {
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
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView.builder(
              itemCount: stations.length,
              itemBuilder: (context, index) {

                final station = stations[index];
                final level = station["latest_reading"]?["water_level"];

                return Card(
                  margin: const EdgeInsets.all(10),
                  child: ListTile(
                    title: Text(station["station_name"]),
                    subtitle: Text(
                        "River: ${station["river_name"] ?? "Unknown"}"),
                    trailing: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text("Level: ${level ?? "N/A"}"),
                        Text(
                          predictFlood(level),
                          style: const TextStyle(
                              fontWeight: FontWeight.bold),
                        )
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }
}