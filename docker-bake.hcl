variable "CI" {
  // Set to true if running in a CI environment (currently unused)
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

variable "CSD_REINGEST" {
  // Whether to reingest the CSD data even if it already exists in the image
  default = "false"
}

variable "CSD_NUM_STRUCTURES" {
  // Number of structures to ingest (default: all)
  default = ""
}

variable "CSD_ACTIVATION_KEY" {
  // Active CSD license key required both as build and runtime
  default = ""
}

variable "CSD_INSTALLER_URL" {
  // Time-limited installer URL required at build time; see README for instructions
  default = ""
}

variable "CSD_ENCRYPTION_KEY" {
  // Optional passphrase used to encrypt the CSD data inside the images (build and runtime);
  // defaults to CSD_ACTIVATION_KEY, and is required when using a licence server
  default = ""
}

variable "CSD_LICENCE_SERVER" {
  // Optional floating licence server URL (e.g., `http://myserver:1234`) to use instead of CSD_ACTIVATION_KEY
  default = ""
}

variable "CSD_DATA_DIR" {
  // Optional path to the root of an existing local CCDC installation (i.e., the directory
  // containing `ccdc-data/csd`); if set, this is used instead of downloading the CSD with the installer
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
    "type=registry,ref=${IMAGE_BASE}-test:cache",
    "type=gha",
  ]
  tags = ["${IMAGE_BASE}-test:${VERSION}"]
  secret = [
    "type=env,id=csd-activation-key,env=CSD_ACTIVATION_KEY",
    "type=env,id=csd-encryption-key,env=CSD_ENCRYPTION_KEY",
    "type=env,id=csd-licence-server,env=CSD_LICENCE_SERVER",
    "id=csd-installer-url,env=CSD_INSTALLER_URL",
  ]
  contexts = CSD_DATA_DIR != "" ? {"csd-data" = CSD_DATA_DIR} : {}
}

target "csd-optimade-dev" {
  inherits = ["docker-metadata-action"]
  context = "."
  dockerfile = "Dockerfile"
  args = {CSD_NUM_STRUCTURES = 1000, REINGEST = CSD_REINGEST}
  target = "csd-optimade-server"
  tags = ["${IMAGE_BASE}-dev:${VERSION}"]
  cache-from = [
    "type=registry,ref=${IMAGE_BASE}:${VERSION}",
    "type=registry,ref=${IMAGE_BASE}:cache",
  ]
  secret = [
    "type=env,id=csd-activation-key,env=CSD_ACTIVATION_KEY",
    "type=env,id=csd-encryption-key,env=CSD_ENCRYPTION_KEY",
    "type=env,id=csd-licence-server,env=CSD_LICENCE_SERVER",
    "id=csd-installer-url,env=CSD_INSTALLER_URL",
  ]
  contexts = CSD_DATA_DIR != "" ? {"csd-data" = CSD_DATA_DIR} : {}
}

target "csd-optimade-server" {
  inherits = ["docker-metadata-action"]
  context = "."
  dockerfile = "Dockerfile"
  args = {CSD_NUM_STRUCTURES = CSD_NUM_STRUCTURES, REINGEST = CSD_REINGEST}
  target = "csd-optimade-server"
  tags = ["${IMAGE_BASE}:${VERSION}"]
  cache-from = [
    "type=registry,ref=${IMAGE_BASE}:${VERSION}",
    "type=registry,ref=${IMAGE_BASE}:cache",
  ]
  secret = [
    "type=env,id=csd-activation-key,env=CSD_ACTIVATION_KEY",
    "type=env,id=csd-encryption-key,env=CSD_ENCRYPTION_KEY",
    "type=env,id=csd-licence-server,env=CSD_LICENCE_SERVER",
    "id=csd-installer-url,env=CSD_INSTALLER_URL",
  ]
  contexts = CSD_DATA_DIR != "" ? {"csd-data" = CSD_DATA_DIR} : {}
}
