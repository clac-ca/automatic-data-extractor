extension microsoftGraphV1

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

@description('PostgreSQL password-auth administrator login name. Used only when postgresqlAuthenticationMode includes password auth.')
param postgresqlAdministratorLogin string = ''

@secure()
@description('PostgreSQL password-auth administrator login password. Required only when postgresqlAuthenticationMode includes password auth.')
param postgresqlAdministratorPassword string = ''

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

@allowed([
  'postgresql_only'
  'microsoft_entra_only'
  'postgresql_and_microsoft_entra'
])
@description('PostgreSQL authentication mode.')
param postgresqlAuthenticationMode string = 'microsoft_entra_only'

@description('Enable PostgreSQL firewall 0.0.0.0 rule to allow public access from Azure services.')
param postgresqlAllowPublicAccessFromAzureServices bool = true

@description('Public IPv4 allowlist applied to PostgreSQL and Storage network rules.')
param publicIpv4Allowlist array = []

@description('Storage account SKU name.')
param storageAccountSkuName string = 'Standard_LRS'

@allowed([
  'microsoft_entra'
  'shared_key'
])
@description('Blob authentication method. microsoft_entra uses managed identity + RBAC, shared_key uses ADE_BLOB_CONNECTION_STRING.')
param storageBlobAuthenticationMethod string = 'microsoft_entra'

@minLength(1)
@description('Access control group name prefix. Group principal names are derived as <prefix>-...')
param accessControlGroupNamePrefix string = 'ade'

@description('When true, create all required Microsoft Entra groups from accessControlGroupNamePrefix and use them for RBAC + database grants.')
param createAccessControlEntraGroups bool = true

@description('Microsoft Entra object ID for <prefix>-rg-owners. Required when createAccessControlEntraGroups=false.')
param resourceGroupOwnersEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-rg-contributors. Required when createAccessControlEntraGroups=false.')
param resourceGroupContributorsEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-rg-readers. Required when createAccessControlEntraGroups=false.')
param resourceGroupReadersEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-ca-admins. Required when createAccessControlEntraGroups=false.')
param containerAppsAdminsEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-ca-operators. Required when createAccessControlEntraGroups=false.')
param containerAppsOperatorsEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-ca-readers. Required when createAccessControlEntraGroups=false.')
param containerAppsReadersEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-db-admins. Required when createAccessControlEntraGroups=false.')
param databaseAdminsEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-db-readwrite. Required when createAccessControlEntraGroups=false.')
param databaseReadWriteEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-db-readonly. Required when createAccessControlEntraGroups=false.')
param databaseReadOnlyEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-st-admins. Required when createAccessControlEntraGroups=false.')
param storageAdminsEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-st-readwrite. Required when createAccessControlEntraGroups=false.')
param storageReadWriteEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for <prefix>-st-readonly. Required when createAccessControlEntraGroups=false.')
param storageReadOnlyEntraGroupObjectId string = ''

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
var postgresqlBootstrapManagedIdentityName = take('id-${workload}-${sharedEnvironmentToken}-${locationToken}-${instance}-postgresql-bootstrap', 128)
var postgresqlBootstrapDeploymentScriptName = take('mod-${workload}-${locationToken}-${instance}-postgresql-bootstrap', 64)

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

var postgresqlUsesMicrosoftEntraAuthentication = contains([
  'microsoft_entra_only'
  'postgresql_and_microsoft_entra'
], postgresqlAuthenticationMode)

var effectivePostgresqlAdministratorLogin = empty(postgresqlAdministratorLogin) ? 'adeadmin' : postgresqlAdministratorLogin

var adeDatabaseAuthenticationMode = postgresqlUsesMicrosoftEntraAuthentication ? 'managed_identity' : 'password'
var storageUsesMicrosoftEntraAuthentication = storageBlobAuthenticationMethod == 'microsoft_entra'

var normalizedAccessControlGroupNamePrefix = toLower(replace(replace(replace(accessControlGroupNamePrefix, ' ', '-'), '_', '-'), '.', '-'))

var resourceGroupOwnersGroupName = '${normalizedAccessControlGroupNamePrefix}-rg-owners'
var resourceGroupContributorsGroupName = '${normalizedAccessControlGroupNamePrefix}-rg-contributors'
var resourceGroupReadersGroupName = '${normalizedAccessControlGroupNamePrefix}-rg-readers'
var containerAppsAdminsGroupName = '${normalizedAccessControlGroupNamePrefix}-ca-admins'
var containerAppsOperatorsGroupName = '${normalizedAccessControlGroupNamePrefix}-ca-operators'
var containerAppsReadersGroupName = '${normalizedAccessControlGroupNamePrefix}-ca-readers'
var databaseAdminsGroupName = '${normalizedAccessControlGroupNamePrefix}-db-admins'
var databaseReadWriteGroupName = '${normalizedAccessControlGroupNamePrefix}-db-readwrite'
var databaseReadOnlyGroupName = '${normalizedAccessControlGroupNamePrefix}-db-readonly'
var storageAdminsGroupName = '${normalizedAccessControlGroupNamePrefix}-st-admins'
var storageReadWriteGroupName = '${normalizedAccessControlGroupNamePrefix}-st-readwrite'
var storageReadOnlyGroupName = '${normalizedAccessControlGroupNamePrefix}-st-readonly'

resource resourceGroupOwnersGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: resourceGroupOwnersGroupName
  displayName: resourceGroupOwnersGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(resourceGroupOwnersGroupName, 64)
}

resource resourceGroupContributorsGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: resourceGroupContributorsGroupName
  displayName: resourceGroupContributorsGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(resourceGroupContributorsGroupName, 64)
}

resource resourceGroupReadersGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: resourceGroupReadersGroupName
  displayName: resourceGroupReadersGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(resourceGroupReadersGroupName, 64)
}

resource containerAppsAdminsGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: containerAppsAdminsGroupName
  displayName: containerAppsAdminsGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(containerAppsAdminsGroupName, 64)
}

resource containerAppsOperatorsGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: containerAppsOperatorsGroupName
  displayName: containerAppsOperatorsGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(containerAppsOperatorsGroupName, 64)
}

resource containerAppsReadersGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: containerAppsReadersGroupName
  displayName: containerAppsReadersGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(containerAppsReadersGroupName, 64)
}

resource databaseAdminsGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: databaseAdminsGroupName
  displayName: databaseAdminsGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(databaseAdminsGroupName, 64)
}

resource databaseReadWriteGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: databaseReadWriteGroupName
  displayName: databaseReadWriteGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(databaseReadWriteGroupName, 64)
}

resource databaseReadOnlyGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: databaseReadOnlyGroupName
  displayName: databaseReadOnlyGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(databaseReadOnlyGroupName, 64)
}

resource storageAdminsGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: storageAdminsGroupName
  displayName: storageAdminsGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(storageAdminsGroupName, 64)
}

resource storageReadWriteGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: storageReadWriteGroupName
  displayName: storageReadWriteGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(storageReadWriteGroupName, 64)
}

resource storageReadOnlyGroup 'Microsoft.Graph/groups@v1.0' = if (createAccessControlEntraGroups) {
  uniqueName: storageReadOnlyGroupName
  displayName: storageReadOnlyGroupName
  securityEnabled: true
  mailEnabled: false
  mailNickname: take(storageReadOnlyGroupName, 64)
}

var effectiveResourceGroupOwnersEntraGroupObjectId = createAccessControlEntraGroups ? resourceGroupOwnersGroup!.id : resourceGroupOwnersEntraGroupObjectId
var effectiveResourceGroupContributorsEntraGroupObjectId = createAccessControlEntraGroups ? resourceGroupContributorsGroup!.id : resourceGroupContributorsEntraGroupObjectId
var effectiveResourceGroupReadersEntraGroupObjectId = createAccessControlEntraGroups ? resourceGroupReadersGroup!.id : resourceGroupReadersEntraGroupObjectId
var effectiveContainerAppsAdminsEntraGroupObjectId = createAccessControlEntraGroups ? containerAppsAdminsGroup!.id : containerAppsAdminsEntraGroupObjectId
var effectiveContainerAppsOperatorsEntraGroupObjectId = createAccessControlEntraGroups ? containerAppsOperatorsGroup!.id : containerAppsOperatorsEntraGroupObjectId
var effectiveContainerAppsReadersEntraGroupObjectId = createAccessControlEntraGroups ? containerAppsReadersGroup!.id : containerAppsReadersEntraGroupObjectId
var effectiveDatabaseAdminsEntraGroupObjectId = createAccessControlEntraGroups ? databaseAdminsGroup!.id : databaseAdminsEntraGroupObjectId
var effectiveDatabaseReadWriteEntraGroupObjectId = createAccessControlEntraGroups ? databaseReadWriteGroup!.id : databaseReadWriteEntraGroupObjectId
var effectiveDatabaseReadOnlyEntraGroupObjectId = createAccessControlEntraGroups ? databaseReadOnlyGroup!.id : databaseReadOnlyEntraGroupObjectId
var effectiveStorageAdminsEntraGroupObjectId = createAccessControlEntraGroups ? storageAdminsGroup!.id : storageAdminsEntraGroupObjectId
var effectiveStorageReadWriteEntraGroupObjectId = createAccessControlEntraGroups ? storageReadWriteGroup!.id : storageReadWriteEntraGroupObjectId
var effectiveStorageReadOnlyEntraGroupObjectId = createAccessControlEntraGroups ? storageReadOnlyGroup!.id : storageReadOnlyEntraGroupObjectId

var hasCompleteProvidedAccessControlGroupObjectIds = !empty(resourceGroupOwnersEntraGroupObjectId) && !empty(resourceGroupContributorsEntraGroupObjectId) && !empty(resourceGroupReadersEntraGroupObjectId) && !empty(containerAppsAdminsEntraGroupObjectId) && !empty(containerAppsOperatorsEntraGroupObjectId) && !empty(containerAppsReadersEntraGroupObjectId) && !empty(databaseAdminsEntraGroupObjectId) && !empty(databaseReadWriteEntraGroupObjectId) && !empty(databaseReadOnlyEntraGroupObjectId) && !empty(storageAdminsEntraGroupObjectId) && !empty(storageReadWriteEntraGroupObjectId) && !empty(storageReadOnlyEntraGroupObjectId)
var hasProvidedDatabaseGroupObjectIds = !empty(databaseReadWriteEntraGroupObjectId) && !empty(databaseReadOnlyEntraGroupObjectId)
var shouldApplyAccessControlRbac = createAccessControlEntraGroups || hasCompleteProvidedAccessControlGroupObjectIds
var shouldApplyDatabaseGroupGrants = createAccessControlEntraGroups || hasProvidedDatabaseGroupObjectIds

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
    postgresqlAdministratorLogin: effectivePostgresqlAdministratorLogin
    postgresqlAdministratorPassword: postgresqlAdministratorPassword
    postgresqlVersion: postgresqlVersion
    postgresqlSkuTier: postgresqlSkuTier
    postgresqlSkuName: postgresqlSkuName
    postgresqlStorageSizeGb: postgresqlStorageSizeGb
    deployDevelopmentEnvironment: deployDevelopmentEnvironment
    postgresqlProductionDatabaseName: postgresqlProductionDatabaseName
    postgresqlDevelopmentDatabaseName: postgresqlDevelopmentDatabaseName
    postgresqlAuthenticationMode: postgresqlAuthenticationMode
    postgresqlAllowPublicAccessFromAzureServices: postgresqlAllowPublicAccessFromAzureServices
    publicIpv4Allowlist: publicIpv4Allowlist
    accessControlGroupNamePrefix: accessControlGroupNamePrefix
    databaseAdminsEntraGroupObjectId: effectiveDatabaseAdminsEntraGroupObjectId
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

var productionDatabaseUrl = postgresqlUsesMicrosoftEntraAuthentication
  ? 'postgresql+psycopg://${productionContainerAppName}@${postgresql.outputs.postgresqlFullyQualifiedDomainName}:5432/${postgresqlProductionDatabaseName}?sslmode=require'
  : 'postgresql+psycopg://${uriComponent(effectivePostgresqlAdministratorLogin)}:${uriComponent(postgresqlAdministratorPassword)}@${postgresql.outputs.postgresqlFullyQualifiedDomainName}:5432/${postgresqlProductionDatabaseName}?sslmode=require'

var developmentDatabaseUrl = postgresqlUsesMicrosoftEntraAuthentication
  ? 'postgresql+psycopg://${developmentContainerAppName}@${postgresql.outputs.postgresqlFullyQualifiedDomainName}:5432/${postgresqlDevelopmentDatabaseName}?sslmode=require'
  : 'postgresql+psycopg://${uriComponent(effectivePostgresqlAdministratorLogin)}:${uriComponent(postgresqlAdministratorPassword)}@${postgresql.outputs.postgresqlFullyQualifiedDomainName}:5432/${postgresqlDevelopmentDatabaseName}?sslmode=require'

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
    containerAppsManagedEnvironmentName: observability.outputs.containerAppsManagedEnvironmentName
    containerAppsManagedEnvironmentResourceId: observability.outputs.containerAppsManagedEnvironmentResourceId
    containerAppsManagedEnvironmentDefaultDomain: observability.outputs.containerAppsManagedEnvironmentDefaultDomain
    storageAccountName: storage.outputs.storageAccountName
    storageFileShareName: storage.outputs.productionFileShareName
    managedEnvironmentStorageName: productionManagedEnvironmentStorageName
    storageBlobAuthenticationMethod: storageBlobAuthenticationMethod
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
    containerAppsManagedEnvironmentName: observability.outputs.containerAppsManagedEnvironmentName
    containerAppsManagedEnvironmentResourceId: observability.outputs.containerAppsManagedEnvironmentResourceId
    containerAppsManagedEnvironmentDefaultDomain: observability.outputs.containerAppsManagedEnvironmentDefaultDomain
    storageAccountName: storage.outputs.storageAccountName
    storageFileShareName: storage.outputs.developmentFileShareName
    managedEnvironmentStorageName: developmentManagedEnvironmentStorageName
    storageBlobAuthenticationMethod: storageBlobAuthenticationMethod
    adeBlobContainerName: storage.outputs.developmentBlobContainerName
    adeDatabaseUrl: developmentDatabaseUrl
    adeDatabaseAuthenticationMode: adeDatabaseAuthenticationMode
  }
}

module accessControlRbac 'modules/access-control-rbac.bicep' = if (shouldApplyAccessControlRbac) {
  name: take('mod-${workload}-${locationToken}-${instance}-access-control-rbac', 64)
  params: {
    deployDevelopmentEnvironment: deployDevelopmentEnvironment
    containerAppsManagedEnvironmentName: observability.outputs.containerAppsManagedEnvironmentName
    logAnalyticsWorkspaceName: observability.outputs.logAnalyticsWorkspaceName
    storageAccountName: storage.outputs.storageAccountName
    postgresqlServerName: postgresql.outputs.postgresqlServerName
    productionContainerAppName: productionContainerApp.outputs.containerAppName
    developmentContainerAppName: developmentContainerApp.outputs.containerAppName
    resourceGroupOwnersEntraGroupObjectId: effectiveResourceGroupOwnersEntraGroupObjectId
    resourceGroupContributorsEntraGroupObjectId: effectiveResourceGroupContributorsEntraGroupObjectId
    resourceGroupReadersEntraGroupObjectId: effectiveResourceGroupReadersEntraGroupObjectId
    containerAppsAdminsEntraGroupObjectId: effectiveContainerAppsAdminsEntraGroupObjectId
    containerAppsOperatorsEntraGroupObjectId: effectiveContainerAppsOperatorsEntraGroupObjectId
    containerAppsReadersEntraGroupObjectId: effectiveContainerAppsReadersEntraGroupObjectId
    databaseAdminsEntraGroupObjectId: effectiveDatabaseAdminsEntraGroupObjectId
    databaseReadWriteEntraGroupObjectId: effectiveDatabaseReadWriteEntraGroupObjectId
    databaseReadOnlyEntraGroupObjectId: effectiveDatabaseReadOnlyEntraGroupObjectId
    storageAdminsEntraGroupObjectId: effectiveStorageAdminsEntraGroupObjectId
    storageReadWriteEntraGroupObjectId: effectiveStorageReadWriteEntraGroupObjectId
    storageReadOnlyEntraGroupObjectId: effectiveStorageReadOnlyEntraGroupObjectId
  }
}

module postgresqlBootstrap 'modules/postgresql-bootstrap.bicep' = if (postgresqlUsesMicrosoftEntraAuthentication) {
  name: take('mod-${workload}-${locationToken}-${instance}-postgresql-bootstrap', 64)
  params: {
    location: location
    postgresqlServerName: postgresql.outputs.postgresqlServerName
    postgresqlBootstrapManagedIdentityName: postgresqlBootstrapManagedIdentityName
    postgresqlBootstrapDeploymentScriptName: postgresqlBootstrapDeploymentScriptName
    deployDevelopmentEnvironment: deployDevelopmentEnvironment
    postgresqlProductionDatabaseName: postgresqlProductionDatabaseName
    postgresqlDevelopmentDatabaseName: postgresqlDevelopmentDatabaseName
    productionContainerAppRoleName: productionContainerApp.outputs.containerAppName
    productionContainerAppObjectId: productionContainerApp.outputs.containerAppPrincipalId
    developmentContainerAppRoleName: developmentContainerApp.outputs.containerAppName
    developmentContainerAppObjectId: developmentContainerApp.outputs.containerAppPrincipalId
    databaseReadWriteEntraGroupObjectId: effectiveDatabaseReadWriteEntraGroupObjectId
    databaseReadOnlyEntraGroupObjectId: effectiveDatabaseReadOnlyEntraGroupObjectId
    applyDatabaseGroupGrants: shouldApplyDatabaseGroupGrants
    accessControlGroupNamePrefix: accessControlGroupNamePrefix
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

resource productionContainerAppBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (storageUsesMicrosoftEntraAuthentication) {
  name: guid(productionBlobContainer.id, productionContainerAppName, storageBlobDataContributorRoleDefinitionResourceId)
  scope: productionBlobContainer
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionResourceId
    principalId: productionContainerApp.outputs.containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource developmentContainerAppBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDevelopmentEnvironment && storageUsesMicrosoftEntraAuthentication) {
  name: guid(developmentBlobContainer!.id, developmentContainerAppName, storageBlobDataContributorRoleDefinitionResourceId)
  scope: developmentBlobContainer!
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionResourceId
    principalId: developmentContainerApp.outputs.containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output deployDevelopmentEnvironment bool = deployDevelopmentEnvironment
output createAccessControlEntraGroups bool = createAccessControlEntraGroups
output accessControlRoleAssignmentsApplied bool = shouldApplyAccessControlRbac
output postgresqlDatabaseGroupGrantsApplied bool = shouldApplyDatabaseGroupGrants
output accessControlGroupObjectIds object = {
  resourceGroupOwners: effectiveResourceGroupOwnersEntraGroupObjectId
  resourceGroupContributors: effectiveResourceGroupContributorsEntraGroupObjectId
  resourceGroupReaders: effectiveResourceGroupReadersEntraGroupObjectId
  containerAppsAdmins: effectiveContainerAppsAdminsEntraGroupObjectId
  containerAppsOperators: effectiveContainerAppsOperatorsEntraGroupObjectId
  containerAppsReaders: effectiveContainerAppsReadersEntraGroupObjectId
  databaseAdmins: effectiveDatabaseAdminsEntraGroupObjectId
  databaseReadWrite: effectiveDatabaseReadWriteEntraGroupObjectId
  databaseReadOnly: effectiveDatabaseReadOnlyEntraGroupObjectId
  storageAdmins: effectiveStorageAdminsEntraGroupObjectId
  storageReadWrite: effectiveStorageReadWriteEntraGroupObjectId
  storageReadOnly: effectiveStorageReadOnlyEntraGroupObjectId
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
output postgresqlAuthenticationMode string = postgresqlAuthenticationMode
output adeDatabaseAuthenticationMode string = adeDatabaseAuthenticationMode
output storageBlobAuthenticationMethod string = storageBlobAuthenticationMethod
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
