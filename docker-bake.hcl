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

group "default" {
  targets = ["csd-ingester-test", "csd-optimade-server"]
}

target "csd-ingester-test" {
  context = "."
  dockerfile = "Dockerfile"
  target = "csd-ingester-test"
  tags = ["${IMAGE_BASE}-test:${VERSION}"]
  secret = CI ? ["type=env,id=env"] : ["type=file,id=env,src=.env"]
}

target "csd-optimade-server" {
  context = "."
  dockerfile = "Dockerfile"
  target = "csd-optimade-server"
  tags = ["${IMAGE_BASE}:${VERSION}"]
  secret = CI ? ["type=env,id=env"] : ["type=file,id=env,src=.env"]
}

target "compress-csd-data" {
  context = "."
  dockerfile = "Dockerfile"
  target = "csd-optimade-server"
  secret = CI ? ["type=env,id=env"] : ["type=file,id=env,src=.env"]
}
