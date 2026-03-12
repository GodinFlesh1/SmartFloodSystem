import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const EcoFloodApp());
}

class EcoFloodApp extends StatelessWidget {
  const EcoFloodApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "EcoFlood",
      theme: ThemeData(primarySwatch: Colors.blue),
      home: const HomeScreen(),
    );
  }
}