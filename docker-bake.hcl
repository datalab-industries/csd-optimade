variable "IMAGE_BASE" {
  default = "ghcr.io/datalab-industries/csd-optimade"
}

variable "VERSION" {
  // Version tag to use for the images
  default = "latest"
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
  secret = ["id=env,src=.env"]
}

target "csd-optimade-server" {
  context = "."
  dockerfile = "Dockerfile"
  target = "csd-optimade-server"
  tags = ["${IMAGE_BASE}:${VERSION}"]
  secret = ["id=env,src=.env"]
}
