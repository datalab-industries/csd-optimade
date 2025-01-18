variable "CI" {
  // Set to true if running in a CI environment; this affects how secrets are mounted
  default = false
}

variable "IMAGE_BASE" {
  // Base image name to use for the images, will be `-test` or not depending on the target
  default = "ghcr.io/datalab-industries/csd-optimade"
}

variable "VERSION" {
  // Version tag to use for the images
  default = "latest"
}

variable "CSD_NUM_STRUCTURES" {
  // Number of structures to ingest (default: all)
  default = 100000
}

variable "CSD_ACTIVATION_KEY" {
  // Active CSD license key required both as build and runtime
  default = ""
}

variable "CSD_INSTALLER_URL" {
  // Time-limited installer URL required at build time; see README for instructions
  default = ""
}

// Used in the CI to appropriately tag the images
// based on events
target "docker-metadata-action" {}

group "default" {
  targets = ["csd-ingester-test", "csd-optimade-server"]
}

target "csd-ingester-test" {
  inherits = ["docker-metadata-action"]
  context = "."
  dockerfile = "Dockerfile"
  target = "csd-ingester-test"
  cache-from = [
    "type=registry,ref=${IMAGE_BASE}-test:${VERSION}",
    "type=registry,ref=${IMAGE_BASE}-test:cache"
  ]
  cache-to = [
    "type=registry,ref=${IMAGE_BASE}-test:cache,mode=max"
  ]
  tags = ["${IMAGE_BASE}-test:${VERSION}"]
  secret = ["type=env,id=csd-activation-key,env=CSD_ACTIVATION_KEY", "id=csd-installer-url,env=CSD_INSTALLER_URL"]
}

target "csd-optimade-server" {
  inherits = ["docker-metadata-action"]
  context = "."
  dockerfile = "Dockerfile"
  args = {CSD_NUM_STRUCTURES = CSD_NUM_STRUCTURES}
  target = "csd-optimade-server"
  tags = ["${IMAGE_BASE}:${VERSION}"]
  cache-from = ["type=registry,ref=${IMAGE_BASE}"]
  secret = ["type=env,id=csd-activation-key,env=CSD_ACTIVATION_KEY", "id=csd-installer-url,env=CSD_INSTALLER_URL"]
}
