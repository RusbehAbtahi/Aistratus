#############################################################
# CloudWatch metrics & alarms for TinyLlama Router Lambda   #
#############################################################

/* ----------------
   Module variables
   ---------------- */
variable "router_function_name" {
  description = "Exact name of the Router Lambda function"
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch log-group name for the Router Lambda"
  type        = string
}

/* ------------------------------
   Metric filter: count 4xx errors
   ------------------------------ */
resource "aws_cloudwatch_log_metric_filter" "error_4xx" {
  name           = "${var.router_function_name}-4xx"
  log_group_name = var.log_group_name
  pattern        = "{$.statusCode = 4*}"

  metric_transformation {
    name      = "Router4xx"
    namespace = "TLFIF/LAM"
    value     = "1"
  }
}

/* --------------------------------
   Alarm: p95 latency > 60 ms (3 min)
   -------------------------------- */
resource "aws_cloudwatch_metric_alarm" "p95_latency" {
  alarm_name          = "${var.router_function_name}-p95-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  extended_statistic           = "p95"
  threshold           = 60
  datapoints_to_alarm = 3
  dimensions = {
    FunctionName = var.router_function_name
  }
  alarm_description = "Router Lambda p95 latency > 60 ms for 3 consecutive minutes"
}

/* -------
   Outputs
   ------- */
output "alarm_name" {
  description = "Name of the p95 latency CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.p95_latency.alarm_name
}