{{- define "iyup.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "iyup.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "iyup.labels" -}}
app.kubernetes.io/name: {{ include "iyup.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "iyup.selectorLabels" -}}
app.kubernetes.io/name: {{ include "iyup.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
