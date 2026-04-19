class PathStep {
  final int gx;
  final int gy;
  final double wx;
  final double wy;
  final double heading;

  const PathStep({
    required this.gx,
    required this.gy,
    required this.wx,
    required this.wy,
    required this.heading,
  });

  factory PathStep.fromJson(Map<String, dynamic> json) => PathStep(
        gx: json['gx'] as int,
        gy: json['gy'] as int,
        wx: (json['wx'] as num).toDouble(),
        wy: (json['wy'] as num).toDouble(),
        heading: (json['heading'] as num).toDouble(),
      );
}
