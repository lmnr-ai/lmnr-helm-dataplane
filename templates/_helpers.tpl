{{/*
Chart name.
*/}}
{{- define "laminar-dataplane.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name (release-based).
*/}}
{{- define "laminar-dataplane.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label value.
*/}}
{{- define "laminar-dataplane.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "laminar-dataplane.labels" -}}
helm.sh/chart: {{ include "laminar-dataplane.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/*
Resource name helper: prefixes with "laminar-" unless already prefixed.
Usage: {{ include "laminar-dataplane.resourceName" "clickhouse" }}
*/}}
{{- define "laminar-dataplane.resourceName" -}}
{{- if hasPrefix "laminar-" . -}}
{{- . -}}
{{- else -}}
{{- printf "laminar-%s" . -}}
{{- end -}}
{{- end }}

{{/*
Selector labels for a specific component.
Usage: {{ include "laminar-dataplane.selectorLabels" (dict "name" "clickhouse" "context" .) }}
*/}}
{{- define "laminar-dataplane.selectorLabels" -}}
app.kubernetes.io/name: {{ include "laminar-dataplane.resourceName" .name }}
app.kubernetes.io/instance: {{ .context.Release.Name }}
{{- end }}

{{/*
Default LoadBalancer annotations based on cloud provider.
Returns a dict of annotations that can be merged with user overrides.
*/}}
{{- define "laminar-dataplane.lbDefaultAnnotations" -}}
{{- if eq .Values.cloudProvider "aws" }}
service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "tcp"
{{- else if eq .Values.cloudProvider "gcp" }}
networking.gke.io/load-balancer-type: "External"
{{- end }}
{{- end }}

{{/*
Merged LoadBalancer annotations: defaults + user overrides.
User-provided annotations in .Values.dataPlaneProxy.loadBalancer.annotations
override any default annotations with the same key.
*/}}
{{- define "laminar-dataplane.lbAnnotations" -}}
{{- $defaults := include "laminar-dataplane.lbDefaultAnnotations" . | fromYaml | default dict }}
{{- $overrides := .Values.dataPlaneProxy.loadBalancer.annotations | default dict }}
{{- $merged := merge $overrides $defaults }}
{{- if $merged }}
{{- toYaml $merged }}
{{- end }}
{{- end }}
