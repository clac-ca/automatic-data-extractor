targetScope = 'resourceGroup'

@description('Azure location for the Container App.')
param location string

@description('Deploy the Container App resources when true.')
param deploy bool

@description('Container App name.')
param containerAppName string

@description('Container App image reference.')
param containerAppImage string

@description('Container App public HTTPS URL mapped to ADE_PUBLIC_WEB_URL. Empty uses the generated default URL.')
param containerAppPublicWebUrl string

@secure()
@description('ADE_SECRET_KEY value for the Container App.')
param containerAppSecretKey string

@description('Additional Container App environment variable overrides.')
param containerAppEnvironmentOverrides object

@minValue(0)
@description('Minimum replica count.')
param containerAppMinimumReplicas int

@minValue(1)
@description('Maximum replica count.')
param containerAppMaximumReplicas int

@description('Container Apps managed environment name.')
param containerAppsManagedEnvironmentName string

@description('Container Apps managed environment resource ID.')
param containerAppsManagedEnvironmentResourceId string

@description('Container Apps managed environment default DNS suffix domain.')
param containerAppsManagedEnvironmentDefaultDomain string

@description('Storage account name used for Azure Files mount and blob access configuration.')
param storageAccountName string

@description('Azure Files share name mounted into the Container App.')
param storageFileShareName string

@description('Managed environment storage mount name.')
param managedEnvironmentStorageName string

@description('Blob container name for ADE_BLOB_CONTAINER.')
param adeBlobContainerName string

@description('Database URL value for ADE_DATABASE_URL.')
param adeDatabaseUrl string

@description('ADE_DATABASE_AUTH_MODE value.')
param adeDatabaseAuthenticationMode string

resource containerAppsManagedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsManagedEnvironmentName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

var storageAccountKey = storageAccount.listKeys().keys[0].value
var defaultContainerAppPublicWebUrl = 'https://${containerAppName}.${containerAppsManagedEnvironmentDefaultDomain}'
var effectiveContainerAppPublicWebUrl = empty(containerAppPublicWebUrl) ? defaultContainerAppPublicWebUrl : containerAppPublicWebUrl
var adeBlobAccountUrl = 'https://${storageAccountName}.blob.${environment().suffixes.storage}'

var managedAdeEnvironmentVariableNames = [
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

var containerAppEnvironmentOverrideEntriesRaw = [for entry in items(containerAppEnvironmentOverrides): {
  name: entry.key
  value: string(entry.value)
}]

var containerAppEnvironmentOverrideEntries = filter(containerAppEnvironmentOverrideEntriesRaw, entry => !contains(managedAdeEnvironmentVariableNames, entry.name))
var containerAppEnvironmentOverrideNames = [for entry in containerAppEnvironmentOverrideEntries: entry.name]

var containerAppBaseEnvironmentVariables = [
  {
    name: 'ADE_SERVICES'
    value: 'api,worker,web'
  }
  {
    name: 'ADE_PUBLIC_WEB_URL'
    value: effectiveContainerAppPublicWebUrl
  }
  {
    name: 'ADE_DATABASE_AUTH_MODE'
    value: adeDatabaseAuthenticationMode
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
    value: adeBlobAccountUrl
  }
  {
    name: 'ADE_BLOB_CONTAINER'
    value: adeBlobContainerName
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

var containerAppBaseEnvironmentVariablesWithoutOverrides = filter(containerAppBaseEnvironmentVariables, entry => !contains(containerAppEnvironmentOverrideNames, entry.name))
var containerAppEnvironmentVariables = concat(containerAppBaseEnvironmentVariablesWithoutOverrides, containerAppEnvironmentOverrideEntries)

var containerAppSecrets = concat(
  [
    {
      name: 'ade-database-url'
      value: adeDatabaseUrl
    }
    {
      name: 'ade-secret-key'
      value: containerAppSecretKey
    }
  ]
)

resource managedEnvironmentStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = if (deploy) {
  parent: containerAppsManagedEnvironment
  name: managedEnvironmentStorageName
  properties: {
    azureFile: {
      accessMode: 'ReadWrite'
      accountName: storageAccountName
      accountKey: storageAccountKey
      shareName: storageFileShareName
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = if (deploy) {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsManagedEnvironmentResourceId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'Auto'
        allowInsecure: false
      }
      secrets: containerAppSecrets
    }
    template: {
      containers: [
        {
          name: containerAppName
          image: containerAppImage
          env: containerAppEnvironmentVariables
          volumeMounts: [
            {
              volumeName: 'ade-data'
              mountPath: '/app/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: containerAppMinimumReplicas
        maxReplicas: containerAppMaximumReplicas
      }
      volumes: [
        {
          name: 'ade-data'
          storageType: 'AzureFile'
          storageName: managedEnvironmentStorageName
        }
      ]
    }
  }
  dependsOn: [
    managedEnvironmentStorage
  ]
}

output containerAppName string = deploy ? containerApp!.name : ''
output containerAppResourceId string = deploy ? containerApp!.id : ''
output containerAppPrincipalId string = deploy ? containerApp!.identity.principalId! : ''
output containerAppFqdn string = deploy ? containerApp!.properties.configuration.ingress.fqdn! : ''
