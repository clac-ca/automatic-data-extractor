targetScope = 'resourceGroup'

@description('Deploy development RBAC assignments when true.')
param deployDevelopmentEnvironment bool

@description('Container Apps managed environment name.')
param containerAppsManagedEnvironmentName string

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string

@description('Storage account name.')
param storageAccountName string

@description('PostgreSQL Flexible Server name.')
param postgresqlServerName string

@description('Production Container App name.')
param productionContainerAppName string

@description('Development Container App name.')
param developmentContainerAppName string

@minLength(1)
@description('Microsoft Entra object ID for the Resource Group owners group.')
param resourceGroupOwnersEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the Resource Group contributors group.')
param resourceGroupContributorsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the Resource Group readers group.')
param resourceGroupReadersEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the Container Apps admins group.')
param containerAppsAdminsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the Container Apps operators group.')
param containerAppsOperatorsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the Container Apps readers group.')
param containerAppsReadersEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the database admins group.')
param databaseAdminsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the database read-write group.')
param databaseReadWriteEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the database read-only group.')
param databaseReadOnlyEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the storage admins group.')
param storageAdminsEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the storage read-write group.')
param storageReadWriteEntraGroupObjectId string

@minLength(1)
@description('Microsoft Entra object ID for the storage read-only group.')
param storageReadOnlyEntraGroupObjectId string

var ownerRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8e3af657-a8ff-443c-a75c-2fe8c4bcb635')
var contributorRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
var readerRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
var containerAppsContributorRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '358470bc-b998-42bd-ab17-a7e34c199c0f')
var containerAppsOperatorRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'f3bd1b5c-91fa-40e7-afe7-0c11d331232c')
var containerAppsManagedEnvironmentContributorRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '57cc5028-e6a7-4284-868d-0611c5923f8d')
var logAnalyticsDataReaderRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3b03c2da-16b3-4a49-8834-0f8130efdd3b')
var storageAccountContributorRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab')
var storageBlobDataContributorRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var storageBlobDataReaderRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')

resource containerAppsManagedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsManagedEnvironmentName
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource postgresqlServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: postgresqlServerName
}

resource productionContainerApp 'Microsoft.App/containerApps@2023-05-01' existing = {
  name: productionContainerAppName
}

resource developmentContainerApp 'Microsoft.App/containerApps@2023-05-01' existing = if (deployDevelopmentEnvironment) {
  name: developmentContainerAppName
}

resource resourceGroupOwnersRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceGroupOwnersEntraGroupObjectId, ownerRoleDefinitionResourceId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: ownerRoleDefinitionResourceId
    principalId: resourceGroupOwnersEntraGroupObjectId
    principalType: 'Group'
  }
}

resource resourceGroupContributorsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceGroupContributorsEntraGroupObjectId, contributorRoleDefinitionResourceId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: contributorRoleDefinitionResourceId
    principalId: resourceGroupContributorsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource resourceGroupReadersRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceGroupReadersEntraGroupObjectId, readerRoleDefinitionResourceId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: resourceGroupReadersEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsAdminsProductionAppRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(productionContainerApp.id, containerAppsAdminsEntraGroupObjectId, containerAppsContributorRoleDefinitionResourceId)
  scope: productionContainerApp
  properties: {
    roleDefinitionId: containerAppsContributorRoleDefinitionResourceId
    principalId: containerAppsAdminsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsAdminsDevelopmentAppRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDevelopmentEnvironment) {
  name: guid(developmentContainerApp!.id, containerAppsAdminsEntraGroupObjectId, containerAppsContributorRoleDefinitionResourceId)
  scope: developmentContainerApp!
  properties: {
    roleDefinitionId: containerAppsContributorRoleDefinitionResourceId
    principalId: containerAppsAdminsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsAdminsManagedEnvironmentRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerAppsManagedEnvironment.id, containerAppsAdminsEntraGroupObjectId, containerAppsManagedEnvironmentContributorRoleDefinitionResourceId)
  scope: containerAppsManagedEnvironment
  properties: {
    roleDefinitionId: containerAppsManagedEnvironmentContributorRoleDefinitionResourceId
    principalId: containerAppsAdminsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsAdminsLogAnalyticsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalyticsWorkspace.id, containerAppsAdminsEntraGroupObjectId, logAnalyticsDataReaderRoleDefinitionResourceId)
  scope: logAnalyticsWorkspace
  properties: {
    roleDefinitionId: logAnalyticsDataReaderRoleDefinitionResourceId
    principalId: containerAppsAdminsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsOperatorsProductionAppRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(productionContainerApp.id, containerAppsOperatorsEntraGroupObjectId, containerAppsOperatorRoleDefinitionResourceId)
  scope: productionContainerApp
  properties: {
    roleDefinitionId: containerAppsOperatorRoleDefinitionResourceId
    principalId: containerAppsOperatorsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsOperatorsDevelopmentAppRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDevelopmentEnvironment) {
  name: guid(developmentContainerApp!.id, containerAppsOperatorsEntraGroupObjectId, containerAppsOperatorRoleDefinitionResourceId)
  scope: developmentContainerApp!
  properties: {
    roleDefinitionId: containerAppsOperatorRoleDefinitionResourceId
    principalId: containerAppsOperatorsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsOperatorsManagedEnvironmentRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerAppsManagedEnvironment.id, containerAppsOperatorsEntraGroupObjectId, readerRoleDefinitionResourceId)
  scope: containerAppsManagedEnvironment
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: containerAppsOperatorsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsOperatorsLogAnalyticsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalyticsWorkspace.id, containerAppsOperatorsEntraGroupObjectId, logAnalyticsDataReaderRoleDefinitionResourceId)
  scope: logAnalyticsWorkspace
  properties: {
    roleDefinitionId: logAnalyticsDataReaderRoleDefinitionResourceId
    principalId: containerAppsOperatorsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsReadersProductionAppRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(productionContainerApp.id, containerAppsReadersEntraGroupObjectId, readerRoleDefinitionResourceId)
  scope: productionContainerApp
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: containerAppsReadersEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsReadersDevelopmentAppRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDevelopmentEnvironment) {
  name: guid(developmentContainerApp!.id, containerAppsReadersEntraGroupObjectId, readerRoleDefinitionResourceId)
  scope: developmentContainerApp!
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: containerAppsReadersEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsReadersManagedEnvironmentRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerAppsManagedEnvironment.id, containerAppsReadersEntraGroupObjectId, readerRoleDefinitionResourceId)
  scope: containerAppsManagedEnvironment
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: containerAppsReadersEntraGroupObjectId
    principalType: 'Group'
  }
}

resource containerAppsReadersLogAnalyticsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalyticsWorkspace.id, containerAppsReadersEntraGroupObjectId, logAnalyticsDataReaderRoleDefinitionResourceId)
  scope: logAnalyticsWorkspace
  properties: {
    roleDefinitionId: logAnalyticsDataReaderRoleDefinitionResourceId
    principalId: containerAppsReadersEntraGroupObjectId
    principalType: 'Group'
  }
}

resource storageAdminsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, storageAdminsEntraGroupObjectId, storageAccountContributorRoleDefinitionResourceId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageAccountContributorRoleDefinitionResourceId
    principalId: storageAdminsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource storageReadWriteRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, storageReadWriteEntraGroupObjectId, storageBlobDataContributorRoleDefinitionResourceId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionResourceId
    principalId: storageReadWriteEntraGroupObjectId
    principalType: 'Group'
  }
}

resource storageReadOnlyRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, storageReadOnlyEntraGroupObjectId, storageBlobDataReaderRoleDefinitionResourceId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageBlobDataReaderRoleDefinitionResourceId
    principalId: storageReadOnlyEntraGroupObjectId
    principalType: 'Group'
  }
}

resource databaseAdminsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(postgresqlServer.id, databaseAdminsEntraGroupObjectId, contributorRoleDefinitionResourceId)
  scope: postgresqlServer
  properties: {
    roleDefinitionId: contributorRoleDefinitionResourceId
    principalId: databaseAdminsEntraGroupObjectId
    principalType: 'Group'
  }
}

resource databaseReadWriteRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(postgresqlServer.id, databaseReadWriteEntraGroupObjectId, readerRoleDefinitionResourceId)
  scope: postgresqlServer
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: databaseReadWriteEntraGroupObjectId
    principalType: 'Group'
  }
}

resource databaseReadOnlyRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(postgresqlServer.id, databaseReadOnlyEntraGroupObjectId, readerRoleDefinitionResourceId)
  scope: postgresqlServer
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: databaseReadOnlyEntraGroupObjectId
    principalType: 'Group'
  }
}
