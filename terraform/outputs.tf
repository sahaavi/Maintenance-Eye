output "storage_bucket" {
  description = "Cloud Storage bucket name"
  value       = google_storage_bucket.storage.name
}
