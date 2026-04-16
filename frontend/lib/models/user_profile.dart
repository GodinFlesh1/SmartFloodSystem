class UserProfile {
  final String id;
  final String? email;
  final bool notificationsEnabled;
  final Map<String, dynamic>? homeLocation;

  const UserProfile({
    required this.id,
    this.email,
    required this.notificationsEnabled,
    this.homeLocation,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as String,
      email: json['email'] as String?,
      notificationsEnabled: (json['notifications_enabled'] as bool?) ?? true,
      homeLocation: json['home_location'] as Map<String, dynamic>?,
    );
  }
}
