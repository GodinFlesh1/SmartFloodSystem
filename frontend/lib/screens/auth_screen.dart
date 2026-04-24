import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _auth = AuthService();
  final _phoneController = TextEditingController(text: '+44');
  final _otpController = TextEditingController();

  bool _loading = false;
  bool _otpSent = false;
  String? _verificationId;
  String? _error;

  @override
  void dispose() {
    _phoneController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  Future<void> _sendOtp() async {
    final phone = _phoneController.text.trim();
    if (phone.isEmpty) return;
    setState(() { _loading = true; _error = null; });

    await _auth.verifyPhoneNumber(
      phoneNumber: phone,
      onCodeSent: (verificationId) {
        setState(() {
          _verificationId = verificationId;
          _otpSent = true;
          _loading = false;
        });
      },
      onError: (msg) {
        setState(() { _error = msg; _loading = false; });
      },
    );
  }

  Future<void> _verifyOtp() async {
    final otp = _otpController.text.trim();
    if (otp.isEmpty || _verificationId == null) return;
    setState(() { _loading = true; _error = null; });

    try {
      await _auth.signInWithOtp(verificationId: _verificationId!, otp: otp);
      // Register this device immediately after sign-in
      await ApiService().registerDevice();
      // authStateChanges in main.dart handles navigation automatically
    } catch (e) {
      setState(() {
        _error = 'Incorrect code. Please try again.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFF0D47A1),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.water, size: 72, color: Colors.white),
              const SizedBox(height: 12),
              const Text(
                'EcoFlood',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Real-time flood early warning',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white70, fontSize: 14),
              ),
              const SizedBox(height: 48),
              if (!_otpSent) ...[
                _label('Phone number'),
                const SizedBox(height: 8),
                _field(
                  controller: _phoneController,
                  hint: '+44 7700 900000',
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 20),
                _button(
                  label: 'Send verification code',
                  onPressed: _loading ? null : _sendOtp,
                ),
              ] else ...[
                _label('Enter the 6-digit code sent to ${_phoneController.text.trim()}'),
                const SizedBox(height: 8),
                _field(
                  controller: _otpController,
                  hint: '000000',
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                ),
                const SizedBox(height: 20),
                _button(
                  label: 'Verify',
                  onPressed: _loading ? null : _verifyOtp,
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: _loading
                      ? null
                      : () => setState(() { _otpSent = false; _error = null; }),
                  child: const Text(
                    'Change number',
                    style: TextStyle(color: Colors.white70),
                  ),
                ),
              ],
              if (_loading) ...[
                const SizedBox(height: 24),
                const Center(child: CircularProgressIndicator(color: Colors.white)),
              ],
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: theme.colorScheme.errorContainer),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _label(String text) => Text(
        text,
        style: const TextStyle(color: Colors.white70, fontSize: 13),
      );

  Widget _field({
    required TextEditingController controller,
    required String hint,
    TextInputType keyboardType = TextInputType.text,
    int? maxLength,
  }) =>
      TextField(
        controller: controller,
        keyboardType: keyboardType,
        maxLength: maxLength,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: const TextStyle(color: Colors.white38),
          counterStyle: const TextStyle(color: Colors.white38),
          filled: true,
          fillColor: Colors.white12,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none,
          ),
        ),
      );

  Widget _button({required String label, required VoidCallback? onPressed}) =>
      ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: const Color(0xFF0D47A1),
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        child: Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
      );
}
