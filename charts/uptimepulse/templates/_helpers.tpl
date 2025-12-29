{{- define "uptimepulse.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "uptimepulse.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "uptimepulse.labels" -}}
app.kubernetes.io/name: {{ include "uptimepulse.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "uptimepulse.selectorLabels" -}}
app.kubernetes.io/name: {{ include "uptimepulse.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
