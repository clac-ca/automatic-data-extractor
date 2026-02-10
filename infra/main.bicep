@minLength(1)
@description('Azure location for deployed resources.')
param location string = resourceGroup().location

@description('Deploy dev resources alongside prod resources.')
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

@description('Prod PostgreSQL database name.')
param postgresProdDb string = 'ade'

@description('Dev PostgreSQL database name.')
param postgresDevDb string = 'ade_dev'

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
param enablePostgresAllowAzureServicesRule bool = true

@description('Allowed public IPv4 addresses for PostgreSQL firewall rules and Azure Storage IP network rules.')
param allowedPublicIpAddresses array = []

@description('Storage account SKU name.')
param storageSku string = 'Standard_LRS'

@description('Prod app container image.')
param prodImage string

@description('Dev app container image. Defaults to prod image when omitted.')
param devImage string = ''

@description('Prod app public URL.')
param prodWebUrl string

@description('Dev app public URL. Defaults to prod URL when omitted.')
param devWebUrl string = ''

@secure()
@description('Prod ADE secret key value.')
param prodSecretKey string

@secure()
@description('Dev ADE secret key value. Defaults to prod secret when omitted.')
param devSecretKey string = ''

@allowed([
  'password'
  'managed_identity'
])
@description('ADE database authentication mode. Use password for quick start or managed_identity for recommended production auth.')
param databaseAuthMode string = 'managed_identity'

@minValue(0)
@description('Prod app minimum replicas.')
param prodMinReplicas int = 1

@minValue(1)
@description('Prod app maximum replicas.')
param prodMaxReplicas int = 2

@minValue(0)
@description('Dev app minimum replicas.')
param devMinReplicas int = 0

@minValue(1)
@description('Dev app maximum replicas.')
param devMaxReplicas int = 1

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

var storageAccountName = toLower('st${uniqueString(subscription().id, resourceGroup().id, workload, regionToken, instance)}')

var prodAppName = take('ca-${workload}-${prodEnvToken}-${regionToken}-${instance}', 32)
var devAppName = take('ca-${workload}-${devEnvToken}-${regionToken}-${instance}', 32)

var prodBlobContainerName = toLower(take('${workload}-${prodEnvToken}', 63))
var devBlobContainerName = toLower(take('${workload}-${devEnvToken}', 63))
var prodFileShareName = toLower(take('${workload}-data-${prodEnvToken}', 63))
var devFileShareName = toLower(take('${workload}-data-${devEnvToken}', 63))

var prodStorageMountName = take('share-${workload}-${prodEnvToken}-${instance}', 32)
var devStorageMountName = take('share-${workload}-${devEnvToken}-${instance}', 32)

var effectiveDevImage = empty(devImage) ? prodImage : devImage
var effectiveDevWebUrl = empty(devWebUrl) ? prodWebUrl : devWebUrl
var effectiveDevSecretKey = empty(devSecretKey) ? prodSecretKey : devSecretKey
var useManagedIdentityDbAuth = databaseAuthMode == 'managed_identity'

var prodDatabaseUrl = useManagedIdentityDbAuth
  ? 'postgresql+psycopg://${prodAppName}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresProdDb}?sslmode=require'
  : 'postgresql+psycopg://${uriComponent(postgresAdminUser)}:${uriComponent(postgresAdminPassword)}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresProdDb}?sslmode=require'
var devDatabaseUrl = useManagedIdentityDbAuth
  ? 'postgresql+psycopg://${devAppName}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresDevDb}?sslmode=require'
  : 'postgresql+psycopg://${uriComponent(postgresAdminUser)}:${uriComponent(postgresAdminPassword)}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${postgresDevDb}?sslmode=require'
var blobAccountUrl = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}'

var allowedIpFirewallRules = [for ip in allowedPublicIpAddresses: {
  name: 'allow-ip-${replace(ip, '.', '-')}'
  startIpAddress: ip
  endIpAddress: ip
}]

var postgresFirewallRules = concat(
  enablePostgresAllowAzureServicesRule
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
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: tenant().tenantId
    }
  }
}

resource postgresProdDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresServer
  name: postgresProdDb
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresDevDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = if (deployDev) {
  parent: postgresServer
  name: postgresDevDb
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

resource postgresEntraAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: postgresServer
  name: postgresEntraAdminObjectId
  properties: {
    principalName: postgresEntraAdminPrincipalName
    principalType: postgresEntraAdminPrincipalType
    tenantId: tenant().tenantId
  }
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

resource devBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDev) {
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

resource devFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = if (deployDev) {
  parent: fileService
  name: devFileShareName
  properties: {
    shareQuota: 1024
  }
}

var storageAccountKey = storageAccount.listKeys().keys[0].value

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

resource devEnvStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = if (deployDev) {
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
      secrets: [
        {
          name: 'ade-database-url'
          value: prodDatabaseUrl
        }
        {
          name: 'ade-secret-key'
          value: prodSecretKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: prodAppName
          image: prodImage
          env: [
            {
              name: 'ADE_SERVICES'
              value: 'api,worker,web'
            }
            {
              name: 'ADE_PUBLIC_WEB_URL'
              value: prodWebUrl
            }
            {
              name: 'ADE_DATABASE_AUTH_MODE'
              value: databaseAuthMode
            }
            {
              name: 'ADE_DATABASE_URL'
              secretRef: 'ade-database-url'
            }
            {
              name: 'ADE_SECRET_KEY'
              secretRef: 'ade-secret-key'
            }
            {
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
          volumeMounts: [
            {
              volumeName: 'ade-data'
              mountPath: '/app/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: prodMinReplicas
        maxReplicas: prodMaxReplicas
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

resource devApp 'Microsoft.App/containerApps@2023-05-01' = if (deployDev) {
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
      secrets: [
        {
          name: 'ade-database-url'
          value: devDatabaseUrl
        }
        {
          name: 'ade-secret-key'
          value: effectiveDevSecretKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: devAppName
          image: effectiveDevImage
          env: [
            {
              name: 'ADE_SERVICES'
              value: 'api,worker,web'
            }
            {
              name: 'ADE_PUBLIC_WEB_URL'
              value: effectiveDevWebUrl
            }
            {
              name: 'ADE_DATABASE_AUTH_MODE'
              value: databaseAuthMode
            }
            {
              name: 'ADE_DATABASE_URL'
              secretRef: 'ade-database-url'
            }
            {
              name: 'ADE_SECRET_KEY'
              secretRef: 'ade-secret-key'
            }
            {
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
          volumeMounts: [
            {
              volumeName: 'ade-data'
              mountPath: '/app/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: devMinReplicas
        maxReplicas: devMaxReplicas
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

var blobRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource prodBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(prodBlobContainer.id, prodApp.name, blobRoleDefinitionId)
  scope: prodBlobContainer
  properties: {
    roleDefinitionId: blobRoleDefinitionId
    principalId: prodApp.identity.principalId!
    principalType: 'ServicePrincipal'
  }
}

resource devBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDev) {
  name: guid(devBlobContainer!.id, devApp!.name, blobRoleDefinitionId)
  scope: devBlobContainer!
  properties: {
    roleDefinitionId: blobRoleDefinitionId
    principalId: devApp!.identity.principalId!
    principalType: 'ServicePrincipal'
  }
}

output deployDev bool = deployDev
output acaEnvName string = managedEnvironment.name
output acaEnvId string = managedEnvironment.id
output vnetName string = vnet.name
output acaSubnetId string = acaSubnet.id
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
output postgresServerName string = postgresServer.name
output postgresFqdn string = postgresServer.properties.fullyQualifiedDomainName
output postgresVersion string = string(postgresServer.properties.version)
output postgresProdDb string = postgresProdDb
output postgresDevDb string = deployDev ? postgresDevDb : ''
output storageAccountName string = storageAccount.name
output prodBlobContainerName string = prodBlobContainerName
output devBlobContainerName string = deployDev ? devBlobContainerName : ''
output prodFileShareName string = prodFileShareName
output devFileShareName string = deployDev ? devFileShareName : ''
output prodAppName string = prodApp.name
output prodAppPrincipalId string = prodApp.identity.principalId!
output prodAppFqdn string = prodApp.properties.configuration.ingress.fqdn!
output devAppName string = deployDev ? devApp!.name : ''
output devAppPrincipalId string = deployDev ? devApp!.identity.principalId! : ''
output devAppFqdn string = deployDev ? devApp!.properties.configuration.ingress.fqdn! : ''
