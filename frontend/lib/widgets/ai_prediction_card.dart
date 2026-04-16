import 'package:flutter/material.dart';
import '../models/flood_prediction.dart';
import '../utils/risk_style.dart';

class AiPredictionCard extends StatelessWidget {
  final FloodPrediction? prediction;
  final bool loading;
  final String? error;

  const AiPredictionCard({
    super.key,
    required this.prediction,
    required this.loading,
    this.error,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        gradient: const LinearGradient(
          colors: [Color(0xFF1565C0), Color(0xFF0D47A1)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF1565C0).withOpacity(0.35),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                const Icon(Icons.psychology, color: Colors.white70, size: 16),
                const SizedBox(width: 6),
                const Text(
                  'AI Flood Prediction · Next 3 Days',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const Spacer(),
                if (loading)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white54,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),

            if (loading && prediction == null)
              const Text(
                'Analysing flood conditions…',
                style: TextStyle(color: Colors.white60, fontSize: 13),
              )
            else if (error != null && prediction == null)
              Row(
                children: [
                  const Icon(Icons.cloud_off, color: Colors.white54, size: 16),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'Prediction unavailable — model not deployed yet.',
                      style: TextStyle(color: Colors.white60, fontSize: 12),
                    ),
                  ),
                ],
              )
            else if (prediction != null)
              _buildPrediction(prediction!),
          ],
        ),
      ),
    );
  }

  Widget _buildPrediction(FloodPrediction p) {
    final risk   = RiskStyle.of(p.riskLevel);
    final pct    = (p.probability * 100).toStringAsFixed(0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Risk level + probability
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            // Risk badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: risk.color.withOpacity(0.25),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: risk.color.withOpacity(0.6)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(risk.icon, size: 14, color: risk.color),
                  const SizedBox(width: 5),
                  Text(
                    risk.label,
                    style: TextStyle(
                      color: risk.color,
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Spacer(),
            // Probability
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '$pct%',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    height: 1,
                  ),
                ),
                Text(
                  'flood probability',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.6),
                    fontSize: 10,
                  ),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 10),

        // Probability bar
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: p.probability,
            backgroundColor: Colors.white.withOpacity(0.15),
            valueColor: AlwaysStoppedAnimation<Color>(risk.color),
            minHeight: 6,
          ),
        ),
        const SizedBox(height: 10),

        // Reason
        Text(
          p.reason,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 13,
            height: 1.4,
          ),
        ),
        const SizedBox(height: 8),

        // Confidence + station
        Row(
          children: [
            Icon(Icons.verified, size: 12,
                color: Colors.white.withOpacity(0.5)),
            const SizedBox(width: 4),
            Text(
              '${p.confidence.toUpperCase()} confidence',
              style: TextStyle(
                color: Colors.white.withOpacity(0.5),
                fontSize: 11,
              ),
            ),
            if (p.topStation.isNotEmpty) ...[
              Text(
                '  ·  ${p.topStation}',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.4),
                  fontSize: 11,
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }
}
