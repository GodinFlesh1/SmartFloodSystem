import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/user_profile.dart';

void main() {
  group('UserProfile.fromJson', () {
    test('parses complete JSON', () {
      final profile = UserProfile.fromJson({
        'id':                    'uuid-1',
        'email':                 'user@example.com',
        'notifications_enabled': true,
        'home_location':         {'lat': 51.5, 'lon': -0.1},
      });

      expect(profile.id,                    'uuid-1');
      expect(profile.email,                 'user@example.com');
      expect(profile.notificationsEnabled,  isTrue);
      expect(profile.homeLocation,          {'lat': 51.5, 'lon': -0.1});
    });

    test('notificationsEnabled defaults to true when missing', () {
      final profile = UserProfile.fromJson({'id': 'uuid-2'});
      expect(profile.notificationsEnabled, isTrue);
    });

    test('email is nullable', () {
      final profile = UserProfile.fromJson({'id': 'uuid-3'});
      expect(profile.email, isNull);
    });

    test('homeLocation is nullable', () {
      final profile = UserProfile.fromJson({'id': 'uuid-4'});
      expect(profile.homeLocation, isNull);
    });

    test('notificationsEnabled can be set to false', () {
      final profile = UserProfile.fromJson({
        'id': 'uuid-5',
        'notifications_enabled': false,
      });
      expect(profile.notificationsEnabled, isFalse);
    });
  });
}
