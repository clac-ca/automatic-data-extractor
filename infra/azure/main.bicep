@minLength(1)
@description('Azure location for deployed resources.')
param location string = resourceGroup().location

@description('Force deploy dev resources alongside prod resources. Optional: when false, dev resources are auto-deployed if any dev-specific parameter differs from its default.')
param deployDev bool = false

@minLength(1)
@description('CAF workload token used in generated names.')
param workload string = 'ade'

@minLength(1)
@description('CAF instance token used in generated names.')
param instance string = '001'

@description('CIDR for the shared virtual network.')
param vnetCidr string = '10.80.0.0/16'

@description('CIDR for the Container Apps delegated subnet.')
param acaSubnetCidr string = '10.80.0.0/23'

@description('PostgreSQL administrator login name.')
param postgresAdminUser string = 'adeadmin'

@secure()
@description('PostgreSQL administrator login password.')
param postgresAdminPassword string

@description('PostgreSQL major version (for example, 16).')
param postgresVersion string = '16'

@description('PostgreSQL tier (for example, Burstable).')
param postgresTier string = 'Burstable'

@description('PostgreSQL SKU name (for example, Standard_B1ms).')
param postgresSkuName string = 'Standard_B1ms'

@minValue(32)
@description('PostgreSQL storage size in GiB.')
param postgresStorageSizeGb int = 32

@description('PostgreSQL production database name.')
param postgresProdDatabaseName string = 'ade'

@description('PostgreSQL development database name.')
param postgresDevDatabaseName string = 'ade_dev'

@description('Entra object ID to set as PostgreSQL Entra admin.')
param postgresEntraAdminObjectId string

@description('Entra principal name (UPN/app/group name) to set as PostgreSQL Entra admin principal name.')
param postgresEntraAdminPrincipalName string

@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
@description('PostgreSQL Entra admin principal type.')
param postgresEntraAdminPrincipalType string = 'User'

@description('Enable PostgreSQL firewall rule equivalent to "Allow public access from any Azure service within Azure to this server" (0.0.0.0 rule).')
param postgresAllowPublicAccessFromAzureServices bool = true

@description('Allowed public IPv4 addresses for PostgreSQL firewall rules and Azure Storage IP network rules.')
param allowedPublicIpAddresses array = []

@description('Storage account SKU name.')
param storageSku string = 'Standard_LRS'

@allowed([
  'postgresql_only'
  'microsoft_entra_only'
  'postgresql_and_microsoft_entra'
])
@description('PostgreSQL Flexible Server authentication mode. postgresql_only enables password auth only, microsoft_entra_only enables Microsoft Entra auth only, and postgresql_and_microsoft_entra enables both.')
param postgresAuthenticationMode string = 'microsoft_entra_only'

@allowed([
  'microsoft_entra'
  'shared_key'
])
@description('Blob data authentication method. microsoft_entra uses managed identity + RBAC; shared_key uses ADE_BLOB_CONNECTION_STRING.')
param storageBlobAuthenticationMethod string = 'microsoft_entra'

@description('Internal force-update token for PostgreSQL Microsoft Entra bootstrap script. Defaults to a new GUID each deployment.')
param postgresEntraBootstrapForceUpdateTag string = newGuid()

@description('Production Container App image.')
param prodContainerAppImage string

@description('Production Container App public HTTPS URL (mapped to `ADE_PUBLIC_WEB_URL`). Leave empty to use the app\'s generated default Container Apps URL.')
param prodContainerAppPublicWebUrl string = ''

@secure()
@description('Container App env var ADE_SECRET_KEY for production.')
param prodContainerAppEnvAdeSecretKey string

@description('Additional production Container App env vars for environment-specific settings (for example ADE_LOG_LEVEL and ADE_LOG_FORMAT).')
param prodContainerAppEnvOverrides object = {}

@minValue(0)
@description('Production Container App minimum replicas.')
param prodContainerAppMinReplicas int = 1

@minValue(1)
@description('Production Container App maximum replicas.')
param prodContainerAppMaxReplicas int = 2

@description('Development Container App image. Defaults to production image when omitted.')
param devContainerAppImage string = ''

@secure()
@description('Container App env var ADE_SECRET_KEY for development. Defaults to production value when omitted.')
param devContainerAppEnvAdeSecretKey string = ''

@description('Development Container App public HTTPS URL (mapped to `ADE_PUBLIC_WEB_URL`). Leave empty to use the app\'s generated default Container Apps URL.')
param devContainerAppPublicWebUrl string = ''

@description('Additional development Container App env vars for environment-specific settings (for example ADE_LOG_LEVEL and ADE_LOG_FORMAT).')
param devContainerAppEnvOverrides object = {}

@minValue(0)
@description('Development Container App minimum replicas.')
param devContainerAppMinReplicas int = 0

@minValue(1)
@description('Development Container App maximum replicas.')
param devContainerAppMaxReplicas int = 1

var regionToken = toLower(replace(location, ' ', ''))
var uniqueShort = toLower(take(uniqueString(subscription().id, resourceGroup().id, workload, regionToken, instance), 4))

var sharedEnvToken = 'shared'
var prodEnvToken = 'prod'
var devEnvToken = 'dev'

var vnetName = take('vnet-${workload}-${sharedEnvToken}-${regionToken}-${instance}', 64)
var acaSubnetName = take('snet-${workload}-${sharedEnvToken}-${regionToken}-${instance}-aca', 80)
var acaEnvName = take('cae-${workload}-${sharedEnvToken}-${regionToken}-${instance}', 60)
var logAnalyticsWorkspaceName = take('log-${workload}-${sharedEnvToken}-${regionToken}-${instance}', 63)
var postgresServerName = take('psql-${workload}-${sharedEnvToken}-${regionToken}-${instance}-${uniqueShort}', 63)
var postgresBootstrapIdentityName = take('id-${workload}-${sharedEnvToken}-${regionToken}-${instance}-pg-bootstrap', 128)
var postgresBootstrapScriptName = take('mod-${workload}-${regionToken}-${instance}-pg-bootstrap', 64)

var storageAccountName = toLower('st${uniqueString(subscription().id, resourceGroup().id, workload, regionToken, instance)}')

var prodAppName = take('ca-${workload}-${prodEnvToken}-${regionToken}-${instance}', 32)
var devAppName = take('ca-${workload}-${devEnvToken}-${regionToken}-${instance}', 32)

var prodBlobContainerName = toLower(take('${workload}-${prodEnvToken}', 63))
var devBlobContainerName = toLower(take('${workload}-${devEnvToken}', 63))
var prodFileShareName = toLower(take('${workload}-data-${prodEnvToken}', 63))
var devFileShareName = toLower(take('${workload}-data-${devEnvToken}', 63))

var prodStorageMountName = take('share-${workload}-${prodEnvToken}-${instance}', 32)
var devStorageMountName = take('share-${workload}-${devEnvToken}-${instance}', 32)

var effectiveDevContainerAppImage = empty(devContainerAppImage) ? prodContainerAppImage : devContainerAppImage
var defaultProdContainerAppPublicWebUrl = 'https://${prodAppName}.${managedEnvironment.properties.defaultDomain}'
var defaultDevContainerAppPublicWebUrl = 'https://${devAppName}.${managedEnvironment.properties.defaultDomain}'
var effectiveProdContainerAppPublicWebUrl = empty(prodContainerAppPublicWebUrl) ? defaultProdContainerAppPublicWebUrl : prodContainerAppPublicWebUrl
var effectiveDevContainerAppPublicWebUrl = empty(devContainerAppPublicWebUrl) ? defaultDevContainerAppPublicWebUrl : devContainerAppPublicWebUrl
var effectiveDevContainerAppEnvAdeSecretKey = empty(devContainerAppEnvAdeSecretKey) ? prodContainerAppEnvAdeSecretKey : devContainerAppEnvAdeSecretKey
var hasDevParameterOverrides = !empty(devContainerAppImage) || !empty(devContainerAppPublicWebUrl) || !empty(devContainerAppEnvAdeSecretKey) || (length(items(devContainerAppEnvOverrides)) > 0) || (devContainerAppMinReplicas != 0) || (devContainerAppMaxReplicas != 1) || (postgresDevDatabaseName != 'ade_dev')
var deployDevEffective = deployDev || hasDevParameterOverrides
var postgresServerUsesEntraAuth = contains([
  'microsoft_entra_only'
  'postgresql_and_microsoft_entra'
], postgresAuthenticationMode)
var postgresServerUsesPasswordAuth = contains([
  'postgresql_only'
  'postgresql_and_microsoft_entra'
], postgresAuthenticationMode)
var useManagedIdentityDatabaseAuth = postgresAuthenticationMode != 'postgresql_only'
var useSharedKeyBlobAuth = storageBlobAuthenticationMethod == 'shared_key'
var useMicrosoftEntraBlobAuth = storageBlobAuthenticationMethod == 'microsoft_entra'
var containerAppEnvAdeDatabaseAuthMode = useManagedIdentityDatabaseAuth ? 'managed_identity' : 'password'

var prodDatabaseUrl = useManagedIdentityDatabaseAuth
  ? 'postgresql+psycopg://${prodAppName}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresProdDatabaseName}?sslmode=require'
  : 'postgresql+psycopg://${uriComponent(postgresAdminUser)}:${uriComponent(postgresAdminPassword)}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresProdDatabaseName}?sslmode=require'
var devDatabaseUrl = useManagedIdentityDatabaseAuth
  ? 'postgresql+psycopg://${devAppName}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresDevDatabaseName}?sslmode=require'
  : 'postgresql+psycopg://${uriComponent(postgresAdminUser)}:${uriComponent(postgresAdminPassword)}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresDevDatabaseName}?sslmode=require'
var blobAccountUrl = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}'
var prodContainerAppEffectiveOverrides = prodContainerAppEnvOverrides
var devContainerAppEffectiveOverrides = devContainerAppEnvOverrides

var managedContainerAppEnvVarNames = [
  'ADE_SERVICES'
  'ADE_PUBLIC_WEB_URL'
  'ADE_API_PROCESSES'
  'ADE_WORKER_RUN_CONCURRENCY'
  'ADE_DATABASE_AUTH_MODE'
  'ADE_DATABASE_URL'
  'ADE_SECRET_KEY'
  'ADE_BLOB_ACCOUNT_URL'
  'ADE_BLOB_CONNECTION_STRING'
  'ADE_BLOB_CONTAINER'
  'ADE_DATA_DIR'
  'ADE_AUTH_DISABLED'
]

var prodContainerAppEnvOverrideEntriesRaw = [for entry in items(prodContainerAppEffectiveOverrides): {
  name: entry.key
  value: string(entry.value)
}]
var prodContainerAppEnvOverrideEntries = filter(prodContainerAppEnvOverrideEntriesRaw, entry => !contains(managedContainerAppEnvVarNames, entry.name))
var prodContainerAppEnvOverrideNames = [for entry in prodContainerAppEnvOverrideEntries: entry.name]

var devContainerAppEnvOverrideEntriesRaw = [for entry in items(devContainerAppEffectiveOverrides): {
  name: entry.key
  value: string(entry.value)
}]
var devContainerAppEnvOverrideEntries = filter(devContainerAppEnvOverrideEntriesRaw, entry => !contains(managedContainerAppEnvVarNames, entry.name))
var devContainerAppEnvOverrideNames = [for entry in devContainerAppEnvOverrideEntries: entry.name]

var prodContainerAppBaseEnv = [
  {
    name: 'ADE_SERVICES'
    value: 'api,worker,web'
  }
  {
    name: 'ADE_PUBLIC_WEB_URL'
    value: effectiveProdContainerAppPublicWebUrl
  }
  {
    name: 'ADE_DATABASE_AUTH_MODE'
    value: containerAppEnvAdeDatabaseAuthMode
  }
  {
    name: 'ADE_DATABASE_URL'
    secretRef: 'ade-database-url'
  }
  {
    name: 'ADE_SECRET_KEY'
    secretRef: 'ade-secret-key'
  }
  useSharedKeyBlobAuth
    ? {
        name: 'ADE_BLOB_CONNECTION_STRING'
        secretRef: 'ade-blob-connection-string'
      }
    : {
        name: 'ADE_BLOB_ACCOUNT_URL'
        value: blobAccountUrl
      }
  {
    name: 'ADE_BLOB_CONTAINER'
    value: prodBlobContainerName
  }
  {
    name: 'ADE_DATA_DIR'
    value: '/app/data'
  }
  {
    name: 'ADE_AUTH_DISABLED'
    value: 'false'
  }
]

var devContainerAppBaseEnv = [
  {
    name: 'ADE_SERVICES'
    value: 'api,worker,web'
  }
  {
    name: 'ADE_PUBLIC_WEB_URL'
    value: effectiveDevContainerAppPublicWebUrl
  }
  {
    name: 'ADE_DATABASE_AUTH_MODE'
    value: containerAppEnvAdeDatabaseAuthMode
  }
  {
    name: 'ADE_DATABASE_URL'
    secretRef: 'ade-database-url'
  }
  {
    name: 'ADE_SECRET_KEY'
    secretRef: 'ade-secret-key'
  }
  useSharedKeyBlobAuth
    ? {
        name: 'ADE_BLOB_CONNECTION_STRING'
        secretRef: 'ade-blob-connection-string'
      }
    : {
        name: 'ADE_BLOB_ACCOUNT_URL'
        value: blobAccountUrl
      }
  {
    name: 'ADE_BLOB_CONTAINER'
    value: devBlobContainerName
  }
  {
    name: 'ADE_DATA_DIR'
    value: '/app/data'
  }
  {
    name: 'ADE_AUTH_DISABLED'
    value: 'false'
  }
]

var prodContainerAppBaseEnvWithoutOverrides = filter(prodContainerAppBaseEnv, entry => !contains(prodContainerAppEnvOverrideNames, entry.name))
var devContainerAppBaseEnvWithoutOverrides = filter(devContainerAppBaseEnv, entry => !contains(devContainerAppEnvOverrideNames, entry.name))
var prodContainerAppEnv = concat(prodContainerAppBaseEnvWithoutOverrides, prodContainerAppEnvOverrideEntries)
var devContainerAppEnv = concat(devContainerAppBaseEnvWithoutOverrides, devContainerAppEnvOverrideEntries)

var allowedIpFirewallRules = [for ip in allowedPublicIpAddresses: {
  name: 'allow-ip-${replace(ip, '.', '-')}'
  startIpAddress: ip
  endIpAddress: ip
}]

var postgresFirewallRules = concat(
  postgresAllowPublicAccessFromAzureServices
    ? [
        {
          name: 'allow-azure-services'
          startIpAddress: '0.0.0.0'
          endIpAddress: '0.0.0.0'
        }
      ]
    : [],
  allowedIpFirewallRules
)

var storageIpRules = [for ip in allowedPublicIpAddresses: {
  action: 'Allow'
  value: ip
}]

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetCidr
      ]
    }
    subnets: [
      {
        name: acaSubnetName
        properties: {
          addressPrefix: acaSubnetCidr
          delegations: [
            {
              name: 'aca-environments-delegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
          serviceEndpoints: [
            {
              service: 'Microsoft.Storage'
            }
          ]
        }
      }
    ]
  }
}

resource acaSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' existing = {
  parent: vnet
  name: acaSubnetName
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      disableLocalAuth: false
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: acaEnvName
  location: location
  properties: {
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: acaSubnet.id
    }
  }
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresServerName
  location: location
  sku: {
    name: postgresSkuName
    tier: postgresTier
  }
  properties: {
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    version: any(postgresVersion)
    storage: {
      storageSizeGB: postgresStorageSizeGb
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    authConfig: {
      activeDirectoryAuth: postgresServerUsesEntraAuth ? 'Enabled' : 'Disabled'
      passwordAuth: postgresServerUsesPasswordAuth ? 'Enabled' : 'Disabled'
      tenantId: tenant().tenantId
    }
  }
}

resource postgresProdDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresServer
  name: postgresProdDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresDevDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = if (deployDevEffective) {
  parent: postgresServer
  name: postgresDevDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresFirewallRuleResources 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = [for rule in postgresFirewallRules: {
  parent: postgresServer
  name: rule.name
  properties: {
    startIpAddress: rule.startIpAddress
    endIpAddress: rule.endIpAddress
  }
}]

resource postgresEntraAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = if (postgresServerUsesEntraAuth) {
  parent: postgresServer
  name: postgresEntraAdminObjectId
  properties: {
    principalName: postgresEntraAdminPrincipalName
    principalType: postgresEntraAdminPrincipalType
    tenantId: tenant().tenantId
  }
}

resource postgresBootstrapIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (useManagedIdentityDatabaseAuth) {
  name: postgresBootstrapIdentityName
  location: location
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: storageSku
  }
  properties: {
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Enabled'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      defaultAction: 'Deny'
      virtualNetworkRules: [
        {
          action: 'Allow'
          id: acaSubnet.id
        }
      ]
      ipRules: storageIpRules
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource prodBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: prodBlobContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource devBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDevEffective) {
  parent: blobService
  name: devBlobContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource prodFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: prodFileShareName
  properties: {
    shareQuota: 1024
  }
}

resource devFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = if (deployDevEffective) {
  parent: fileService
  name: devFileShareName
  properties: {
    shareQuota: 1024
  }
}

var storageAccountKey = storageAccount.listKeys().keys[0].value
var blobConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccountKey};EndpointSuffix=${environment().suffixes.storage}'

var prodContainerAppSecrets = concat(
  [
    {
      name: 'ade-database-url'
      value: prodDatabaseUrl
    }
    {
      name: 'ade-secret-key'
      value: prodContainerAppEnvAdeSecretKey
    }
  ],
  useSharedKeyBlobAuth
    ? [
        {
          name: 'ade-blob-connection-string'
          value: blobConnectionString
        }
      ]
    : []
)

var devContainerAppSecrets = concat(
  [
    {
      name: 'ade-database-url'
      value: devDatabaseUrl
    }
    {
      name: 'ade-secret-key'
      value: effectiveDevContainerAppEnvAdeSecretKey
    }
  ],
  useSharedKeyBlobAuth
    ? [
        {
          name: 'ade-blob-connection-string'
          value: blobConnectionString
        }
      ]
    : []
)

resource prodEnvStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = {
  parent: managedEnvironment
  name: prodStorageMountName
  properties: {
    azureFile: {
      accessMode: 'ReadWrite'
      accountName: storageAccount.name
      accountKey: storageAccountKey
      shareName: prodFileShareName
    }
  }
}

resource devEnvStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = if (deployDevEffective) {
  parent: managedEnvironment
  name: devStorageMountName
  properties: {
    azureFile: {
      accessMode: 'ReadWrite'
      accountName: storageAccount.name
      accountKey: storageAccountKey
      shareName: devFileShareName
    }
  }
}

resource prodApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: prodAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'Auto'
        allowInsecure: false
      }
      secrets: prodContainerAppSecrets
    }
    template: {
      containers: [
        {
          name: prodAppName
          image: prodContainerAppImage
          env: prodContainerAppEnv
          volumeMounts: [
            {
              volumeName: 'ade-data'
              mountPath: '/app/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: prodContainerAppMinReplicas
        maxReplicas: prodContainerAppMaxReplicas
      }
      volumes: [
        {
          name: 'ade-data'
          storageType: 'AzureFile'
          storageName: prodStorageMountName
        }
      ]
    }
  }
}

resource devApp 'Microsoft.App/containerApps@2023-05-01' = if (deployDevEffective) {
  name: devAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'Auto'
        allowInsecure: false
      }
      secrets: devContainerAppSecrets
    }
    template: {
      containers: [
        {
          name: devAppName
          image: effectiveDevContainerAppImage
          env: devContainerAppEnv
          volumeMounts: [
            {
              volumeName: 'ade-data'
              mountPath: '/app/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: devContainerAppMinReplicas
        maxReplicas: devContainerAppMaxReplicas
      }
      volumes: [
        {
          name: 'ade-data'
          storageType: 'AzureFile'
          storageName: devStorageMountName
        }
      ]
    }
  }
}

var postgresBootstrapReaderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
var postgresBootstrapScriptForceUpdateTag = guid(postgresEntraBootstrapForceUpdateTag, prodApp.identity.principalId!, deployDevEffective ? devApp!.identity.principalId! : 'none')

resource postgresBootstrapEntraAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = if (useManagedIdentityDatabaseAuth) {
  parent: postgresServer
  name: postgresBootstrapIdentity!.name
  properties: {
    principalName: postgresBootstrapIdentity!.name
    principalType: 'ServicePrincipal'
    tenantId: tenant().tenantId
  }
}

resource postgresBootstrapReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useManagedIdentityDatabaseAuth) {
  name: guid(postgresServer.id, postgresBootstrapIdentity!.id, postgresBootstrapReaderRoleDefinitionId)
  scope: postgresServer
  properties: {
    roleDefinitionId: postgresBootstrapReaderRoleDefinitionId
    principalId: postgresBootstrapIdentity!.properties.principalId!
    principalType: 'ServicePrincipal'
  }
}

resource postgresManagedIdentityRoleBootstrap 'Microsoft.Resources/deploymentScripts@2023-08-01' = if (useManagedIdentityDatabaseAuth) {
  name: postgresBootstrapScriptName
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${postgresBootstrapIdentity!.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.63.0'
    cleanupPreference: 'OnSuccess'
    retentionInterval: 'P1D'
    timeout: 'PT30M'
    forceUpdateTag: postgresBootstrapScriptForceUpdateTag
    environmentVariables: [
      {
        name: 'POSTGRES_SERVER_NAME'
        value: postgresServer.name
      }
      {
        name: 'POSTGRES_ENTRA_ADMIN_LOGIN'
        value: postgresBootstrapIdentity!.name
      }
      {
        name: 'PROD_APP_ROLE_NAME'
        value: prodApp.name
      }
      {
        name: 'PROD_APP_OBJECT_ID'
        value: prodApp.identity.principalId!
      }
      {
        name: 'PROD_DB_NAME'
        value: postgresProdDatabaseName
      }
      {
        name: 'DEPLOY_DEV'
        value: string(deployDevEffective)
      }
      {
        name: 'DEV_APP_ROLE_NAME'
        value: deployDevEffective ? devApp!.name : ''
      }
      {
        name: 'DEV_APP_OBJECT_ID'
        value: deployDevEffective ? devApp!.identity.principalId! : ''
      }
      {
        name: 'DEV_DB_NAME'
        value: deployDevEffective ? postgresDevDatabaseName : ''
      }
    ]
    scriptContent: '''
set -euo pipefail

az extension add --name rdbms-connect --upgrade --only-show-errors >/dev/null 2>&1 || true

PG_TOKEN="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"

run_sql_with_retry() {
  local sql_text="$1"
  local max_attempts=20
  local wait_seconds=15
  local attempt=1

  while true; do
    if az postgres flexible-server execute \
      --name "$POSTGRES_SERVER_NAME" \
      --admin-user "$POSTGRES_ENTRA_ADMIN_LOGIN" \
      --admin-password "$PG_TOKEN" \
      --database-name postgres \
      --querytext "$sql_text" \
      --only-show-errors \
      --output none; then
      return 0
    fi

    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "SQL execution failed after $max_attempts attempts." >&2
      return 1
    fi

    echo "SQL execution attempt $attempt/$max_attempts failed; retrying in $wait_seconds seconds..."
    sleep "$wait_seconds"
    attempt=$((attempt + 1))
    PG_TOKEN="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"
  done
}

PROD_CREATE_ROLE_SQL="DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$PROD_APP_ROLE_NAME') THEN PERFORM pg_catalog.pgaadauth_create_principal_with_oid('$PROD_APP_ROLE_NAME', '$PROD_APP_OBJECT_ID', 'service', false, false); END IF; END \$\$;"
PROD_GRANT_DB_SQL="GRANT CONNECT, CREATE, TEMP ON DATABASE \"$PROD_DB_NAME\" TO \"$PROD_APP_ROLE_NAME\";"

run_sql_with_retry "$PROD_CREATE_ROLE_SQL"
run_sql_with_retry "$PROD_GRANT_DB_SQL"

if [ "$DEPLOY_DEV" = "true" ]; then
  DEV_CREATE_ROLE_SQL="DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$DEV_APP_ROLE_NAME') THEN PERFORM pg_catalog.pgaadauth_create_principal_with_oid('$DEV_APP_ROLE_NAME', '$DEV_APP_OBJECT_ID', 'service', false, false); END IF; END \$\$;"
  DEV_GRANT_DB_SQL="GRANT CONNECT, CREATE, TEMP ON DATABASE \"$DEV_DB_NAME\" TO \"$DEV_APP_ROLE_NAME\";"
  run_sql_with_retry "$DEV_CREATE_ROLE_SQL"
  run_sql_with_retry "$DEV_GRANT_DB_SQL"
fi

echo "{\"prodRole\":\"$PROD_APP_ROLE_NAME\",\"deployDev\":\"$DEPLOY_DEV\"}" > "$AZ_SCRIPTS_OUTPUT_PATH"
'''
  }
  dependsOn: [
    postgresBootstrapEntraAdmin
    postgresBootstrapReaderRoleAssignment
  ]
}

var blobRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource prodBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useMicrosoftEntraBlobAuth) {
  name: guid(prodBlobContainer.id, prodApp.name, blobRoleDefinitionId)
  scope: prodBlobContainer
  properties: {
    roleDefinitionId: blobRoleDefinitionId
    principalId: prodApp.identity.principalId!
    principalType: 'ServicePrincipal'
  }
}

resource devBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDevEffective && useMicrosoftEntraBlobAuth) {
  name: guid(devBlobContainer!.id, devApp!.name, blobRoleDefinitionId)
  scope: devBlobContainer!
  properties: {
    roleDefinitionId: blobRoleDefinitionId
    principalId: devApp!.identity.principalId!
    principalType: 'ServicePrincipal'
  }
}

output deployDev bool = deployDevEffective
output acaEnvName string = managedEnvironment.name
output acaEnvId string = managedEnvironment.id
output vnetName string = vnet.name
output acaSubnetId string = acaSubnet.id
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
output postgresServerName string = postgresServer.name
output postgresFqdn string = postgresServer.properties.fullyQualifiedDomainName
output postgresVersion string = string(postgresServer.properties.version)
output postgresAuthenticationMode string = postgresAuthenticationMode
output containerAppEnvAdeDatabaseAuthMode string = containerAppEnvAdeDatabaseAuthMode
output storageBlobAuthenticationMethod string = storageBlobAuthenticationMethod
output postgresProdDatabaseName string = postgresProdDatabaseName
output postgresDevDatabaseName string = deployDevEffective ? postgresDevDatabaseName : ''
output storageAccountName string = storageAccount.name
output prodBlobContainerName string = prodBlobContainerName
output devBlobContainerName string = deployDevEffective ? devBlobContainerName : ''
output prodFileShareName string = prodFileShareName
output devFileShareName string = deployDevEffective ? devFileShareName : ''
output prodAppName string = prodApp.name
output prodAppPrincipalId string = prodApp.identity.principalId!
output prodAppFqdn string = prodApp.properties.configuration.ingress.fqdn!
output devAppName string = deployDevEffective ? devApp!.name : ''
output devAppPrincipalId string = deployDevEffective ? devApp!.identity.principalId! : ''
output devAppFqdn string = deployDevEffective ? devApp!.properties.configuration.ingress.fqdn! : ''
