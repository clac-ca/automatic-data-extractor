using './main.bicep'

param location = 'canadacentral'
param deployDev = true
param workload = 'ade'
param instance = '001'

param postgresAdminUser = 'adeadmin'
param postgresAdminPassword = 'change-me-postgres-password'
param postgresEntraAdminObjectId = '00000000-0000-0000-0000-000000000000'
param postgresEntraAdminPrincipalName = 'operator@example.com'
param postgresEntraAdminPrincipalType = 'User'

param enableFabricAzureServicesRule = true
param operatorIps = [
  '203.0.113.10'
]

param prodImage = 'ghcr.io/clac-ca/automatic-data-extractor:vX.Y.Z'
param prodWebUrl = 'https://ade.example.com'
param prodSecretKey = 'change-me-prod-secret-key-32-bytes-min'

param devImage = 'ghcr.io/clac-ca/automatic-data-extractor:vX.Y.Z'
param devWebUrl = 'https://ade-dev.example.com'
param devSecretKey = 'change-me-dev-secret-key-32-bytes-min'
