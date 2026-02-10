@description('Azure location for all resources.')
param location string

@description('Deploy dev resources alongside prod resources.')
param deployDev bool = true

@description('Virtual network name.')
param vnetName string

@description('Container Apps subnet name inside the VNet.')
param acaSubnetName string

@description('Container Apps environment name.')
param acaEnvName string

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string

@description('PostgreSQL flexible server name.')
param postgresServerName string

@description('Storage account name.')
param storageAccountName string

@description('Prod Container App name.')
param prodAppName string

@description('Dev Container App name.')
param devAppName string = ''

@description('ACA environment storage mount name for prod app.')
param prodStorageMountName string

@description('ACA environment storage mount name for dev app.')
param devStorageMountName string = ''

@description('VNet CIDR range.')
param vnetCidr string

@description('ACA subnet CIDR range.')
param acaSubnetCidr string

@description('PostgreSQL administrator login name.')
param postgresAdminUser string

@secure()
@description('PostgreSQL administrator login password.')
param postgresAdminPassword string

@description('PostgreSQL major version to provision (for example, 18).')
param postgresVersionMajor string

@description('PostgreSQL tier (for example, Burstable).')
param postgresTier string

@description('PostgreSQL SKU name (for example, Standard_B1ms).')
param postgresSkuName string

@minValue(32)
@description('PostgreSQL storage size in GiB.')
param postgresStorageSizeGb int

@description('Prod PostgreSQL database name.')
param postgresProdDb string

@description('Dev PostgreSQL database name.')
param postgresDevDb string = ''

@description('Signed-in Entra object ID to set as PostgreSQL Entra admin.')
param postgresEntraAdminObjectId string

@description('Signed-in Entra display name to set as PostgreSQL Entra admin principal name.')
param postgresEntraAdminPrincipalName string

@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
@description('PostgreSQL Entra admin principal type.')
param postgresEntraAdminPrincipalType string = 'User'

@description('Enable the PostgreSQL 0.0.0.0 allow-azure-services firewall rule for Fabric compatibility.')
param enableFabricAzureServicesRule bool = true

@description('Operator IPv4 addresses to allow in PostgreSQL and Storage firewall rules.')
param operatorIps array = []

@description('Storage account SKU name.')
param storageSku string

@description('Prod blob container name.')
param blobProdContainer string

@description('Dev blob container name.')
param blobDevContainer string = ''

@description('Prod Azure Files share name.')
param fileProdShare string

@description('Dev Azure Files share name.')
param fileDevShare string = ''

@description('Prod app image reference.')
param prodImage string

@description('Dev app image reference.')
param devImage string = ''

@description('Prod public web URL.')
param prodWebUrl string

@description('Dev public web URL.')
param devWebUrl string = ''

@secure()
@description('Prod ADE secret key value.')
param prodSecretKey string

@secure()
@description('Dev ADE secret key value.')
param devSecretKey string = ''

@description('ADE database authentication mode.')
param databaseAuthMode string = 'managed_identity'

@description('Prod app minimum replicas.')
param prodMinReplicas int = 1

@description('Prod app maximum replicas.')
param prodMaxReplicas int = 2

@description('Dev app minimum replicas.')
param devMinReplicas int = 0

@description('Dev app maximum replicas.')
param devMaxReplicas int = 1

@description('Prod DB role/user name used in ADE_DATABASE_URL.')
param prodDbRoleName string

@description('Dev DB role/user name used in ADE_DATABASE_URL.')
param devDbRoleName string = ''

var operatorFirewallRules = [for ip in operatorIps: {
  name: 'operator-${replace(ip, '.', '-')}'
  startIpAddress: ip
  endIpAddress: ip
}]

var postgresFirewallRules = concat(
  enableFabricAzureServicesRule
    ? [
        {
          name: 'allow-azure-services'
          startIpAddress: '0.0.0.0'
          endIpAddress: '0.0.0.0'
        }
      ]
    : [],
  operatorFirewallRules
)

var storageIpRules = [for ip in operatorIps: {
  action: 'Allow'
  value: ip
}]

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

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: acaEnvName
  location: location
  properties: {
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

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' = {
  name: postgresServerName
  location: location
  sku: {
    name: postgresSkuName
    tier: postgresTier
  }
  properties: {
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    version: any(postgresVersionMajor)
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

resource postgresProdDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: postgresServer
  name: postgresProdDb
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresDevDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = if (deployDev) {
  parent: postgresServer
  name: postgresDevDb
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresFirewallRuleResources 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = [for rule in postgresFirewallRules: {
  parent: postgresServer
  name: rule.name
  properties: {
    startIpAddress: rule.startIpAddress
    endIpAddress: rule.endIpAddress
  }
}]

resource postgresEntraAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2025-08-01' = {
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

resource prodBlobContainerResource 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: blobProdContainer
  properties: {
    publicAccess: 'None'
  }
}

resource devBlobContainerResource 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDev) {
  parent: blobService
  name: blobDevContainer
  properties: {
    publicAccess: 'None'
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource prodFileShareResource 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: fileProdShare
  properties: {
    shareQuota: 1024
  }
}

resource devFileShareResource 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = if (deployDev) {
  parent: fileService
  name: fileDevShare
  properties: {
    shareQuota: 1024
  }
}

var storageAccountKey = storageAccount.listKeys().keys[0].value
var postgresFqdn = postgresServer.properties.fullyQualifiedDomainName
var prodDatabaseUrl = 'postgresql+psycopg://${prodDbRoleName}@${postgresFqdn}:5432/${postgresProdDb}?sslmode=require'
var devDatabaseUrl = 'postgresql+psycopg://${devDbRoleName}@${postgresFqdn}:5432/${postgresDevDb}?sslmode=require'

resource prodEnvStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = {
  parent: containerAppsEnvironment
  name: prodStorageMountName
  properties: {
    azureFile: {
      accessMode: 'ReadWrite'
      accountName: storageAccount.name
      accountKey: storageAccountKey
      shareName: fileProdShare
    }
  }
}

resource devEnvStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = if (deployDev) {
  parent: containerAppsEnvironment
  name: devStorageMountName
  properties: {
    azureFile: {
      accessMode: 'ReadWrite'
      accountName: storageAccount.name
      accountKey: storageAccountKey
      shareName: fileDevShare
    }
  }
}

resource prodContainerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: prodAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
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
              value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
            }
            {
              name: 'ADE_BLOB_CONTAINER'
              value: blobProdContainer
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

resource devContainerApp 'Microsoft.App/containerApps@2023-05-01' = if (deployDev) {
  name: devAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
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
          value: devSecretKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: devAppName
          image: devImage
          env: [
            {
              name: 'ADE_SERVICES'
              value: 'api,worker,web'
            }
            {
              name: 'ADE_PUBLIC_WEB_URL'
              value: devWebUrl
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
              value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
            }
            {
              name: 'ADE_BLOB_CONTAINER'
              value: blobDevContainer
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

output acaEnvId string = containerAppsEnvironment.id
output logAnalyticsWorkspaceCustomerId string = logAnalyticsWorkspace.properties.customerId
output postgresFqdn string = postgresFqdn
output postgresVersion string = postgresServer.properties.version
output prodAppPrincipalId string = prodContainerApp.identity.principalId
output devAppPrincipalId string = deployDev ? devContainerApp!.identity.principalId : ''
output prodAppFqdn string = prodContainerApp.properties.configuration.ingress.fqdn
output devAppFqdn string = deployDev ? devContainerApp!.properties.configuration.ingress.fqdn : ''
