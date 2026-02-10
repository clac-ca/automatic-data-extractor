targetScope = 'resourceGroup'

@description('Azure location for bootstrap resources.')
param location string

@description('PostgreSQL Flexible Server name.')
param postgresqlServerName string

@description('Bootstrap user-assigned managed identity name.')
param postgresqlBootstrapManagedIdentityName string

@description('Deployment script resource name for PostgreSQL bootstrap.')
param postgresqlBootstrapDeploymentScriptName string

@description('Deploy development DB grants when true.')
param deployDevelopmentEnvironment bool

@description('Production PostgreSQL database name.')
param postgresqlProductionDatabaseName string

@description('Development PostgreSQL database name.')
param postgresqlDevelopmentDatabaseName string

@description('Production Container App role name (mapped to principal role in PostgreSQL).')
param productionContainerAppRoleName string

@description('Production Container App managed identity object ID.')
param productionContainerAppObjectId string

@description('Development Container App role name (mapped to principal role in PostgreSQL).')
param developmentContainerAppRoleName string

@description('Development Container App managed identity object ID.')
param developmentContainerAppObjectId string

@description('Microsoft Entra object ID for database read-write group. Optional when applyDatabaseGroupGrants=false.')
param databaseReadWriteEntraGroupObjectId string = ''

@description('Microsoft Entra object ID for database read-only group. Optional when applyDatabaseGroupGrants=false.')
param databaseReadOnlyEntraGroupObjectId string = ''

@description('Apply database group principal creation and grants for db-readwrite/db-readonly groups.')
param applyDatabaseGroupGrants bool = false

@minLength(1)
@description('Access control group name prefix used to derive DB group principal names.')
param accessControlGroupNamePrefix string

var normalizedAccessControlGroupNamePrefix = toLower(accessControlGroupNamePrefix)
var databaseReadWriteEntraGroupPrincipalName = '${normalizedAccessControlGroupNamePrefix}-db-readwrite'
var databaseReadOnlyEntraGroupPrincipalName = '${normalizedAccessControlGroupNamePrefix}-db-readonly'

var postgresqlBootstrapReaderRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
var postgresqlBootstrapDeploymentScriptForceUpdateTag = guid(
  postgresqlServerName,
  productionContainerAppObjectId,
  deployDevelopmentEnvironment ? developmentContainerAppObjectId : 'none',
  string(applyDatabaseGroupGrants),
  databaseReadWriteEntraGroupObjectId,
  databaseReadOnlyEntraGroupObjectId
)

resource postgresqlServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: postgresqlServerName
}

resource postgresqlBootstrapManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: postgresqlBootstrapManagedIdentityName
  location: location
}

resource postgresqlBootstrapEntraAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: postgresqlServer
  name: postgresqlBootstrapManagedIdentity.name
  properties: {
    principalName: postgresqlBootstrapManagedIdentity.name
    principalType: 'ServicePrincipal'
    tenantId: tenant().tenantId
  }
}

resource postgresqlBootstrapReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(postgresqlServer.id, postgresqlBootstrapManagedIdentity.id, postgresqlBootstrapReaderRoleDefinitionResourceId)
  scope: postgresqlServer
  properties: {
    roleDefinitionId: postgresqlBootstrapReaderRoleDefinitionResourceId
    principalId: postgresqlBootstrapManagedIdentity.properties.principalId!
    principalType: 'ServicePrincipal'
  }
}

resource postgresqlManagedIdentityBootstrapScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: postgresqlBootstrapDeploymentScriptName
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${postgresqlBootstrapManagedIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.63.0'
    cleanupPreference: 'OnSuccess'
    retentionInterval: 'P1D'
    timeout: 'PT30M'
    forceUpdateTag: postgresqlBootstrapDeploymentScriptForceUpdateTag
    environmentVariables: [
      {
        name: 'POSTGRESQL_SERVER_NAME'
        value: postgresqlServer.name
      }
      {
        name: 'POSTGRESQL_ENTRA_BOOTSTRAP_ADMIN_LOGIN'
        value: postgresqlBootstrapManagedIdentity.name
      }
      {
        name: 'PRODUCTION_CONTAINER_APP_ROLE_NAME'
        value: productionContainerAppRoleName
      }
      {
        name: 'PRODUCTION_CONTAINER_APP_OBJECT_ID'
        value: productionContainerAppObjectId
      }
      {
        name: 'PRODUCTION_DATABASE_NAME'
        value: postgresqlProductionDatabaseName
      }
      {
        name: 'DEPLOY_DEVELOPMENT_ENVIRONMENT'
        value: string(deployDevelopmentEnvironment)
      }
      {
        name: 'DEVELOPMENT_CONTAINER_APP_ROLE_NAME'
        value: deployDevelopmentEnvironment ? developmentContainerAppRoleName : ''
      }
      {
        name: 'DEVELOPMENT_CONTAINER_APP_OBJECT_ID'
        value: deployDevelopmentEnvironment ? developmentContainerAppObjectId : ''
      }
      {
        name: 'DEVELOPMENT_DATABASE_NAME'
        value: deployDevelopmentEnvironment ? postgresqlDevelopmentDatabaseName : ''
      }
      {
        name: 'APPLY_DATABASE_GROUP_GRANTS'
        value: string(applyDatabaseGroupGrants)
      }
      {
        name: 'DATABASE_READWRITE_ROLE_NAME'
        value: applyDatabaseGroupGrants ? databaseReadWriteEntraGroupPrincipalName : ''
      }
      {
        name: 'DATABASE_READWRITE_OBJECT_ID'
        value: applyDatabaseGroupGrants ? databaseReadWriteEntraGroupObjectId : ''
      }
      {
        name: 'DATABASE_READONLY_ROLE_NAME'
        value: applyDatabaseGroupGrants ? databaseReadOnlyEntraGroupPrincipalName : ''
      }
      {
        name: 'DATABASE_READONLY_OBJECT_ID'
        value: applyDatabaseGroupGrants ? databaseReadOnlyEntraGroupObjectId : ''
      }
    ]
    scriptContent: loadTextContent('../scripts/postgresql-entra-bootstrap.sh')
  }
  dependsOn: [
    postgresqlBootstrapEntraAdmin
    postgresqlBootstrapReaderRoleAssignment
  ]
}
