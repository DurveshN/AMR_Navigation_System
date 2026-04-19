class MapConfig {
  final double resolution;
  final double widthMeters;
  final double heightMeters;
  final int gridWidth;
  final int gridHeight;
  final double originX;
  final double originY;

  const MapConfig({
    required this.resolution,
    required this.widthMeters,
    required this.heightMeters,
    required this.gridWidth,
    required this.gridHeight,
    required this.originX,
    required this.originY,
  });

  factory MapConfig.fromJson(Map<String, dynamic> json) => MapConfig(
        resolution: (json['resolution'] as num).toDouble(),
        widthMeters: (json['width_meters'] as num).toDouble(),
        heightMeters: (json['height_meters'] as num).toDouble(),
        gridWidth: json['grid_width'] as int,
        gridHeight: json['grid_height'] as int,
        originX: (json['origin_x'] as num).toDouble(),
        originY: (json['origin_y'] as num).toDouble(),
      );
}
