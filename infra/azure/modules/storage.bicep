targetScope = 'resourceGroup'

@description('Azure location for storage resources.')
param location string

@description('Storage account name.')
param storageAccountName string

@description('Storage account SKU name.')
param storageAccountSkuName string

@description('Resource ID of the Container Apps delegated subnet.')
param containerAppsSubnetResourceId string

@description('Public IPv4 allowlist applied to storage network rules.')
param publicIpv4Allowlist array

@description('Deploy development storage resources when true.')
param deployDevelopmentEnvironment bool

@description('Production blob container name.')
param productionBlobContainerName string

@description('Development blob container name.')
param developmentBlobContainerName string

@description('Production Azure Files share name.')
param productionFileShareName string

@description('Development Azure Files share name.')
param developmentFileShareName string

var storageIpRules = [for ipAddress in publicIpv4Allowlist: {
  action: 'Allow'
  value: ipAddress
}]

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: storageAccountSkuName
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
          id: containerAppsSubnetResourceId
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

resource productionBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: productionBlobContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource developmentBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDevelopmentEnvironment) {
  parent: blobService
  name: developmentBlobContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource productionFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: productionFileShareName
  properties: {
    shareQuota: 1024
  }
}

resource developmentFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = if (deployDevelopmentEnvironment) {
  parent: fileService
  name: developmentFileShareName
  properties: {
    shareQuota: 1024
  }
}

output storageAccountName string = storageAccount.name
output storageAccountResourceId string = storageAccount.id
output productionBlobContainerName string = productionBlobContainer.name
output productionBlobContainerResourceId string = productionBlobContainer.id
output developmentBlobContainerName string = deployDevelopmentEnvironment ? developmentBlobContainer!.name : ''
output developmentBlobContainerResourceId string = deployDevelopmentEnvironment ? developmentBlobContainer!.id : ''
output productionFileShareName string = productionFileShare.name
output developmentFileShareName string = deployDevelopmentEnvironment ? developmentFileShare!.name : ''
