class AlertMetrics:
    def __init__(self, area, alert_type, start_time, end_time, severity):
        self.area = area  # area affected
        self.alert_type = alert_type  # rain, snow, wind
        self.start_time = start_time
        self.end_time = end_time
        self.severity = severity  # yellow, orange, red
