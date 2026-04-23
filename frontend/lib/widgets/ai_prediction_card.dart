import 'package:flutter/material.dart';
import '../models/flood_prediction.dart';
import '../utils/risk_style.dart';

class AiPredictionCard extends StatefulWidget {
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
  State<AiPredictionCard> createState() => _AiPredictionCardState();
}

class _AiPredictionCardState extends State<AiPredictionCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulse;
  late Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _opacity = Tween<double>(begin: 0.4, end: 1.0).animate(
      CurvedAnimation(parent: _pulse, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

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
            // Header row
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
                if (widget.loading)
                  AnimatedBuilder(
                    animation: _opacity,
                    builder: (_, __) => Opacity(
                      opacity: _opacity.value,
                      child: const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),

            // Body
            if (widget.loading && widget.prediction == null)
              _buildLoadingState()
            else if (widget.error != null && widget.prediction == null)
              _buildErrorState()
            else if (widget.prediction != null)
              _buildPrediction(widget.prediction!),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingState() {
    return AnimatedBuilder(
      animation: _opacity,
      builder: (_, __) => Opacity(
        opacity: _opacity.value,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.stream, color: Colors.white54, size: 16),
                const SizedBox(width: 8),
                const Text(
                  'Analysing flood conditions…',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            _skeletonBar(width: double.infinity, height: 6),
            const SizedBox(height: 6),
            _skeletonBar(width: 200, height: 10),
            const SizedBox(height: 4),
            _skeletonBar(width: 160, height: 10),
            const SizedBox(height: 10),
            Text(
              'Checking river levels, rainfall and 3-day forecast…',
              style: TextStyle(
                color: Colors.white.withOpacity(0.55),
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _skeletonBar({required double width, required double height}) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.18),
        borderRadius: BorderRadius.circular(4),
      ),
    );
  }

  Widget _buildErrorState() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.wifi_off_rounded,
                  color: Colors.white70, size: 16),
            ),
            const SizedBox(width: 10),
            const Expanded(
              child: Text(
                'Prediction temporarily unavailable',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'We\'re having trouble reaching the prediction service. '
          'This usually resolves in a few seconds — pull down to refresh.',
          style: TextStyle(
            color: Colors.white.withOpacity(0.65),
            fontSize: 12,
            height: 1.4,
          ),
        ),
      ],
    );
  }

  Widget _buildPrediction(FloodPrediction p) {
    final risk = RiskStyle.of(p.riskLevel);
    final pct  = (p.probability * 100).toStringAsFixed(0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Risk badge + probability
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
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

        // Reason text
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
            Icon(Icons.verified,
                size: 12, color: Colors.white.withOpacity(0.5)),
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
