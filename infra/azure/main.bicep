@minLength(1)
@description('Azure location for deployed resources.')
param location string = resourceGroup().location

@minLength(1)
@description('CAF workload token used in generated names.')
param workload string = 'ade'

@minLength(1)
@description('CAF instance token used in generated names.')
param instance string = '001'

@description('Deploy the optional development environment when true.')
param deployDevelopmentEnvironment bool = false

@description('Virtual Network address prefix in CIDR notation.')
param virtualNetworkAddressPrefix string = '10.80.0.0/16'

@description('Container Apps delegated subnet address prefix in CIDR notation.')
param containerAppsSubnetAddressPrefix string = '10.80.0.0/23'

@description('PostgreSQL major version (for example, 16).')
param postgresqlVersion string = '16'

@description('PostgreSQL compute tier (for example, Burstable).')
param postgresqlSkuTier string = 'Burstable'

@description('PostgreSQL SKU name (for example, Standard_B1ms).')
param postgresqlSkuName string = 'Standard_B1ms'

@minValue(32)
@description('PostgreSQL storage size in GiB.')
param postgresqlStorageSizeGb int = 32

@description('Production PostgreSQL database name.')
param postgresqlProductionDatabaseName string = 'ade'

@description('Development PostgreSQL database name.')
param postgresqlDevelopmentDatabaseName string = 'ade_dev'

@description('Enable PostgreSQL firewall 0.0.0.0 rule to allow public access from Azure services.')
param postgresqlAllowPublicAccessFromAzureServices bool = true

@description('Public IPv4 allowlist applied to PostgreSQL and Storage network rules.')
param publicIpv4Allowlist array = []

@description('Storage account SKU name.')
param storageAccountSkuName string = 'Standard_LRS'

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-rg-owners.')
param resourceGroupOwnersEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-rg-contributors.')
param resourceGroupContributorsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-rg-readers.')
param resourceGroupReadersEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-ca-admins.')
param containerAppsAdminsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-ca-operators.')
param containerAppsOperatorsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-ca-readers.')
param containerAppsReadersEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-db-admins.')
param databaseAdminsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-db-readwrite.')
param databaseReadWriteEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-db-readonly.')
param databaseReadOnlyEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-st-admins.')
param storageAdminsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-st-readwrite.')
param storageReadWriteEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for <prefix>-st-readonly.')
param storageReadOnlyEntraGroupObjectId string

@description('Production Container App image.')
param productionContainerAppImage string

@description('Production Container App public HTTPS URL mapped to ADE_PUBLIC_WEB_URL. Empty uses generated default URL.')
param productionContainerAppPublicWebUrl string = ''

@secure()
@description('Production ADE_SECRET_KEY value.')
param productionContainerAppSecretKey string

@description('Production Container App environment variable overrides.')
param productionContainerAppEnvironmentOverrides object = {}

@minValue(0)
@description('Production Container App minimum replicas.')
param productionContainerAppMinimumReplicas int = 1

@minValue(1)
@description('Production Container App maximum replicas.')
param productionContainerAppMaximumReplicas int = 2

@minValue(1)
@description('Production Container App scale polling interval in seconds.')
param productionContainerAppScalePollingIntervalSeconds int = 30

@minValue(0)
@description('Production Container App scale cooldown period in seconds before scaling to minimum replicas.')
param productionContainerAppScaleCooldownPeriodSeconds int = 300

@minValue(1)
@description('Production Container App HTTP concurrent requests threshold per replica for autoscaling.')
param productionContainerAppScaleHttpConcurrentRequests int = 10

@description('Development Container App image. Empty reuses production image.')
param developmentContainerAppImage string = ''

@description('Development Container App public HTTPS URL mapped to ADE_PUBLIC_WEB_URL. Empty uses generated default URL.')
param developmentContainerAppPublicWebUrl string = ''

@secure()
@description('Development ADE_SECRET_KEY value. Empty reuses production secret key.')
param developmentContainerAppSecretKey string = ''

@description('Development Container App environment variable overrides.')
param developmentContainerAppEnvironmentOverrides object = {}

@minValue(0)
@description('Development Container App minimum replicas.')
param developmentContainerAppMinimumReplicas int = 0

@minValue(1)
@description('Development Container App maximum replicas.')
param developmentContainerAppMaximumReplicas int = 1

@minValue(1)
@description('Development Container App scale polling interval in seconds.')
param developmentContainerAppScalePollingIntervalSeconds int = 30

@minValue(0)
@description('Development Container App scale cooldown period in seconds before scaling to minimum replicas.')
param developmentContainerAppScaleCooldownPeriodSeconds int = 1800

@minValue(1)
@description('Development Container App HTTP concurrent requests threshold per replica for autoscaling.')
param developmentContainerAppScaleHttpConcurrentRequests int = 10

var locationToken = toLower(replace(location, ' ', ''))
var locationShortToken = take(locationToken, 3)
var deterministicResourceSuffix = toLower(take(uniqueString(resourceGroup().id), 5))
var normalizedWorkloadToken = toLower(replace(replace(replace(replace(workload, '-', ''), '_', ''), ' ', ''), '.', ''))
var normalizedInstanceToken = toLower(replace(replace(replace(replace(instance, '-', ''), '_', ''), ' ', ''), '.', ''))
var postgresqlWorkloadToken = toLower(replace(replace(replace(workload, '_', '-'), ' ', '-'), '.', '-'))
var postgresqlInstanceToken = toLower(replace(replace(replace(instance, '_', '-'), ' ', '-'), '.', '-'))

var sharedEnvironmentToken = 'shared'
var sharedEnvironmentShortToken = 'sh'
var productionEnvironmentToken = 'prod'
var developmentEnvironmentToken = 'dev'

var virtualNetworkName = take('vnet-${workload}-${sharedEnvironmentToken}-${locationToken}-${instance}', 64)
var containerAppsSubnetName = take('snet-${workload}-${sharedEnvironmentToken}-${locationToken}-${instance}-aca', 80)
var containerAppsManagedEnvironmentName = take('cae-${workload}-${sharedEnvironmentToken}-${locationToken}-${instance}', 60)
var logAnalyticsWorkspaceName = take('log-${workload}-${sharedEnvironmentToken}-${locationToken}-${instance}', 63)
var postgresqlServerName = take('psql-${postgresqlWorkloadToken}-${sharedEnvironmentToken}-${locationToken}-${postgresqlInstanceToken}-${deterministicResourceSuffix}', 63)

var storageAccountName = toLower(take('st${normalizedWorkloadToken}${sharedEnvironmentShortToken}${locationShortToken}${normalizedInstanceToken}${deterministicResourceSuffix}', 24))

var productionContainerAppName = take('ca-${workload}-${productionEnvironmentToken}-${locationToken}-${instance}', 32)
var developmentContainerAppName = take('ca-${workload}-${developmentEnvironmentToken}-${locationToken}-${instance}', 32)

var productionBlobContainerName = toLower(take('${workload}-${productionEnvironmentToken}', 63))
var developmentBlobContainerName = toLower(take('${workload}-${developmentEnvironmentToken}', 63))
var productionFileShareName = toLower(take('${workload}-data-${productionEnvironmentToken}', 63))
var developmentFileShareName = toLower(take('${workload}-data-${developmentEnvironmentToken}', 63))

var productionManagedEnvironmentStorageName = take('share-${workload}-${productionEnvironmentToken}-${instance}', 32)
var developmentManagedEnvironmentStorageName = take('share-${workload}-${developmentEnvironmentToken}-${instance}', 32)

var effectiveDevelopmentContainerAppImage = empty(developmentContainerAppImage) ? productionContainerAppImage : developmentContainerAppImage
var effectiveDevelopmentContainerAppSecretKey = empty(developmentContainerAppSecretKey) ? productionContainerAppSecretKey : developmentContainerAppSecretKey

var adeDatabaseAuthenticationMode = 'managed_identity'

module networking 'modules/networking.bicep' = {
  name: take('mod-${workload}-${locationToken}-${instance}-networking', 64)
  params: {
    location: location
    virtualNetworkName: virtualNetworkName
    virtualNetworkAddressPrefix: virtualNetworkAddressPrefix
    containerAppsSubnetName: containerAppsSubnetName
    containerAppsSubnetAddressPrefix: containerAppsSubnetAddressPrefix
  }
}

module observability 'modules/observability.bicep' = {
  name: take('mod-${workload}-${locationToken}-${instance}-observability', 64)
  params: {
    location: location
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    containerAppsManagedEnvironmentName: containerAppsManagedEnvironmentName
    containerAppsInfrastructureSubnetResourceId: networking.outputs.containerAppsSubnetResourceId
  }
}

module postgresql 'modules/postgresql.bicep' = {
  name: take('mod-${workload}-${locationToken}-${instance}-postgresql', 64)
  params: {
    location: location
    postgresqlServerName: postgresqlServerName
    postgresqlVersion: postgresqlVersion
    postgresqlSkuTier: postgresqlSkuTier
    postgresqlSkuName: postgresqlSkuName
    postgresqlStorageSizeGb: postgresqlStorageSizeGb
    deployDevelopmentEnvironment: deployDevelopmentEnvironment
    postgresqlProductionDatabaseName: postgresqlProductionDatabaseName
    postgresqlDevelopmentDatabaseName: postgresqlDevelopmentDatabaseName
    postgresqlAllowPublicAccessFromAzureServices: postgresqlAllowPublicAccessFromAzureServices
    publicIpv4Allowlist: publicIpv4Allowlist
  }
}

module storage 'modules/storage.bicep' = {
  name: take('mod-${workload}-${locationToken}-${instance}-storage', 64)
  params: {
    location: location
    storageAccountName: storageAccountName
    storageAccountSkuName: storageAccountSkuName
    containerAppsSubnetResourceId: networking.outputs.containerAppsSubnetResourceId
    publicIpv4Allowlist: publicIpv4Allowlist
    deployDevelopmentEnvironment: deployDevelopmentEnvironment
    productionBlobContainerName: productionBlobContainerName
    developmentBlobContainerName: developmentBlobContainerName
    productionFileShareName: productionFileShareName
    developmentFileShareName: developmentFileShareName
  }
}

var productionDatabaseUrl = 'postgresql+psycopg://${productionContainerAppName}@${postgresql.outputs.postgresqlFullyQualifiedDomainName}:5432/${postgresqlProductionDatabaseName}?sslmode=require'
var developmentDatabaseUrl = 'postgresql+psycopg://${developmentContainerAppName}@${postgresql.outputs.postgresqlFullyQualifiedDomainName}:5432/${postgresqlDevelopmentDatabaseName}?sslmode=require'

module productionContainerApp 'modules/container-app.bicep' = {
  name: take('mod-${workload}-${locationToken}-${instance}-container-app-production', 64)
  params: {
    location: location
    deploy: true
    containerAppName: productionContainerAppName
    containerAppImage: productionContainerAppImage
    containerAppPublicWebUrl: productionContainerAppPublicWebUrl
    containerAppSecretKey: productionContainerAppSecretKey
    containerAppEnvironmentOverrides: productionContainerAppEnvironmentOverrides
    containerAppMinimumReplicas: productionContainerAppMinimumReplicas
    containerAppMaximumReplicas: productionContainerAppMaximumReplicas
    containerAppScalePollingIntervalSeconds: productionContainerAppScalePollingIntervalSeconds
    containerAppScaleCooldownPeriodSeconds: productionContainerAppScaleCooldownPeriodSeconds
    containerAppScaleHttpConcurrentRequests: productionContainerAppScaleHttpConcurrentRequests
    containerAppsManagedEnvironmentName: observability.outputs.containerAppsManagedEnvironmentName
    containerAppsManagedEnvironmentResourceId: observability.outputs.containerAppsManagedEnvironmentResourceId
    containerAppsManagedEnvironmentDefaultDomain: observability.outputs.containerAppsManagedEnvironmentDefaultDomain
    storageAccountName: storage.outputs.storageAccountName
    storageFileShareName: storage.outputs.productionFileShareName
    managedEnvironmentStorageName: productionManagedEnvironmentStorageName
    adeBlobContainerName: storage.outputs.productionBlobContainerName
    adeDatabaseUrl: productionDatabaseUrl
    adeDatabaseAuthenticationMode: adeDatabaseAuthenticationMode
  }
}

module developmentContainerApp 'modules/container-app.bicep' = {
  name: take('mod-${workload}-${locationToken}-${instance}-container-app-development', 64)
  params: {
    location: location
    deploy: deployDevelopmentEnvironment
    containerAppName: developmentContainerAppName
    containerAppImage: effectiveDevelopmentContainerAppImage
    containerAppPublicWebUrl: developmentContainerAppPublicWebUrl
    containerAppSecretKey: effectiveDevelopmentContainerAppSecretKey
    containerAppEnvironmentOverrides: developmentContainerAppEnvironmentOverrides
    containerAppMinimumReplicas: developmentContainerAppMinimumReplicas
    containerAppMaximumReplicas: developmentContainerAppMaximumReplicas
    containerAppScalePollingIntervalSeconds: developmentContainerAppScalePollingIntervalSeconds
    containerAppScaleCooldownPeriodSeconds: developmentContainerAppScaleCooldownPeriodSeconds
    containerAppScaleHttpConcurrentRequests: developmentContainerAppScaleHttpConcurrentRequests
    containerAppsManagedEnvironmentName: observability.outputs.containerAppsManagedEnvironmentName
    containerAppsManagedEnvironmentResourceId: observability.outputs.containerAppsManagedEnvironmentResourceId
    containerAppsManagedEnvironmentDefaultDomain: observability.outputs.containerAppsManagedEnvironmentDefaultDomain
    storageAccountName: storage.outputs.storageAccountName
    storageFileShareName: storage.outputs.developmentFileShareName
    managedEnvironmentStorageName: developmentManagedEnvironmentStorageName
    adeBlobContainerName: storage.outputs.developmentBlobContainerName
    adeDatabaseUrl: developmentDatabaseUrl
    adeDatabaseAuthenticationMode: adeDatabaseAuthenticationMode
  }
}

module accessControlRbac 'modules/access-control-rbac.bicep' = {
  name: take('mod-${workload}-${locationToken}-${instance}-access-control-rbac', 64)
  params: {
    deployDevelopmentEnvironment: deployDevelopmentEnvironment
    containerAppsManagedEnvironmentName: observability.outputs.containerAppsManagedEnvironmentName
    logAnalyticsWorkspaceName: observability.outputs.logAnalyticsWorkspaceName
    storageAccountName: storage.outputs.storageAccountName
    postgresqlServerName: postgresql.outputs.postgresqlServerName
    productionContainerAppName: productionContainerApp.outputs.containerAppName
    developmentContainerAppName: developmentContainerApp.outputs.containerAppName
    resourceGroupOwnersEntraGroupObjectId: resourceGroupOwnersEntraGroupObjectId
    resourceGroupContributorsEntraGroupObjectId: resourceGroupContributorsEntraGroupObjectId
    resourceGroupReadersEntraGroupObjectId: resourceGroupReadersEntraGroupObjectId
    containerAppsAdminsEntraGroupObjectId: containerAppsAdminsEntraGroupObjectId
    containerAppsOperatorsEntraGroupObjectId: containerAppsOperatorsEntraGroupObjectId
    containerAppsReadersEntraGroupObjectId: containerAppsReadersEntraGroupObjectId
    databaseAdminsEntraGroupObjectId: databaseAdminsEntraGroupObjectId
    databaseReadWriteEntraGroupObjectId: databaseReadWriteEntraGroupObjectId
    databaseReadOnlyEntraGroupObjectId: databaseReadOnlyEntraGroupObjectId
    storageAdminsEntraGroupObjectId: storageAdminsEntraGroupObjectId
    storageReadWriteEntraGroupObjectId: storageReadWriteEntraGroupObjectId
    storageReadOnlyEntraGroupObjectId: storageReadOnlyEntraGroupObjectId
  }
}

var storageBlobDataContributorRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource storageAccountResource 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: storageAccountResource
  name: 'default'
}

resource productionBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  parent: blobService
  name: productionBlobContainerName
}

resource developmentBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = if (deployDevelopmentEnvironment) {
  parent: blobService
  name: developmentBlobContainerName
}

resource productionContainerAppBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(productionBlobContainer.id, productionContainerAppName, storageBlobDataContributorRoleDefinitionResourceId)
  scope: productionBlobContainer
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionResourceId
    principalId: productionContainerApp.outputs.containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource developmentContainerAppBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDevelopmentEnvironment) {
  name: guid(developmentBlobContainer!.id, developmentContainerAppName, storageBlobDataContributorRoleDefinitionResourceId)
  scope: developmentBlobContainer!
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionResourceId
    principalId: developmentContainerApp.outputs.containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output deployDevelopmentEnvironment bool = deployDevelopmentEnvironment
output accessControlRoleAssignmentsApplied bool = true
output accessControlGroupObjectIds object = {
  resourceGroupOwners: resourceGroupOwnersEntraGroupObjectId
  resourceGroupContributors: resourceGroupContributorsEntraGroupObjectId
  resourceGroupReaders: resourceGroupReadersEntraGroupObjectId
  containerAppsAdmins: containerAppsAdminsEntraGroupObjectId
  containerAppsOperators: containerAppsOperatorsEntraGroupObjectId
  containerAppsReaders: containerAppsReadersEntraGroupObjectId
  databaseAdmins: databaseAdminsEntraGroupObjectId
  databaseReadWrite: databaseReadWriteEntraGroupObjectId
  databaseReadOnly: databaseReadOnlyEntraGroupObjectId
  storageAdmins: storageAdminsEntraGroupObjectId
  storageReadWrite: storageReadWriteEntraGroupObjectId
  storageReadOnly: storageReadOnlyEntraGroupObjectId
}
output virtualNetworkName string = networking.outputs.virtualNetworkName
output virtualNetworkResourceId string = networking.outputs.virtualNetworkResourceId
output containerAppsSubnetResourceId string = networking.outputs.containerAppsSubnetResourceId
output logAnalyticsWorkspaceName string = observability.outputs.logAnalyticsWorkspaceName
output logAnalyticsWorkspaceResourceId string = observability.outputs.logAnalyticsWorkspaceResourceId
output containerAppsManagedEnvironmentName string = observability.outputs.containerAppsManagedEnvironmentName
output containerAppsManagedEnvironmentResourceId string = observability.outputs.containerAppsManagedEnvironmentResourceId
output postgresqlServerName string = postgresql.outputs.postgresqlServerName
output postgresqlServerResourceId string = postgresql.outputs.postgresqlServerResourceId
output postgresqlFullyQualifiedDomainName string = postgresql.outputs.postgresqlFullyQualifiedDomainName
output adeDatabaseAuthenticationMode string = adeDatabaseAuthenticationMode
output postgresqlProductionDatabaseName string = postgresqlProductionDatabaseName
output postgresqlDevelopmentDatabaseName string = deployDevelopmentEnvironment ? postgresqlDevelopmentDatabaseName : ''
output storageAccountName string = storage.outputs.storageAccountName
output productionBlobContainerName string = storage.outputs.productionBlobContainerName
output developmentBlobContainerName string = deployDevelopmentEnvironment ? storage.outputs.developmentBlobContainerName : ''
output productionFileShareName string = storage.outputs.productionFileShareName
output developmentFileShareName string = deployDevelopmentEnvironment ? storage.outputs.developmentFileShareName : ''
output productionContainerAppName string = productionContainerApp.outputs.containerAppName
output productionContainerAppPrincipalId string = productionContainerApp.outputs.containerAppPrincipalId
output productionContainerAppFqdn string = productionContainerApp.outputs.containerAppFqdn
output developmentContainerAppName string = developmentContainerApp.outputs.containerAppName
output developmentContainerAppPrincipalId string = developmentContainerApp.outputs.containerAppPrincipalId
output developmentContainerAppFqdn string = developmentContainerApp.outputs.containerAppFqdn
