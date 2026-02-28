# Outputs for the deployment
output "service_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.app.uri
}

output "storage_bucket" {
  description = "Cloud Storage bucket name"
  value       = google_storage_bucket.storage.name
}
