variable "cloud" {
  type        = string
  description = "Cloud provider. One of: aws, azure, gcp."

  validation {
    condition     = contains(["aws", "azure", "gcp"], var.cloud)
    error_message = "cloud must be one of: aws, azure, gcp. Got: \"${var.cloud}\"."
  }
}

variable "regions" {
  type        = list(string)
  description = "Region names to scope CIDRs to (e.g. [\"us-east-1\"]). Empty list = use the all-cloud feed (broader, not recommended for production)."
  default     = []

  validation {
    condition     = alltrue([for r in var.regions : can(regex("^[a-z0-9-]+$", r))])
    error_message = "regions must contain only lowercase letters, digits, and hyphens. Examples: us-east-1, eastus, us-central1."
  }
}

variable "source_base_url" {
  type        = string
  description = "Base URL serving pre-generated CIDR feeds. Override only for forks, mirrors, or self-hosted copies."
  default     = "https://bhavink.github.io/databricksIPranges/output"

  validation {
    condition     = can(regex("^https?://", var.source_base_url))
    error_message = "source_base_url must start with http:// or https://."
  }
}

variable "source_files" {
  type        = list(string)
  description = "Optional list of local CIDR-per-line file paths. If non-empty, the module reads these instead of fetching source_base_url. Use for airgapped or vendored installs."
  default     = []
}

variable "min_cidr_count" {
  type        = number
  description = "Refuse to apply if fewer than this many CIDRs resolve. Guards against empty or corrupted feeds clearing all your firewall rules and locking you out. Set to 0 to disable."
  default     = 1

  validation {
    condition     = var.min_cidr_count >= 0
    error_message = "min_cidr_count must be >= 0."
  }
}
