import 'package:flutter/material.dart';
import 'screens/shell_screen.dart';

void main() {
  runApp(const EcoFloodApp());
}

class EcoFloodApp extends StatelessWidget {
  const EcoFloodApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'EcoFlood',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1565C0)),
        useMaterial3: true,
      ),
      home: const ShellScreen(),
    );
  }
}
