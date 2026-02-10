targetScope = 'resourceGroup'

@description('Azure location for observability resources.')
param location string

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string

@description('Container Apps managed environment name.')
param containerAppsManagedEnvironmentName string

@description('Resource ID of the delegated subnet for Container Apps infrastructure.')
param containerAppsInfrastructureSubnetResourceId string

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

resource containerAppsManagedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppsManagedEnvironmentName
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
      infrastructureSubnetId: containerAppsInfrastructureSubnetResourceId
    }
  }
}

output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
output logAnalyticsWorkspaceResourceId string = logAnalyticsWorkspace.id
output containerAppsManagedEnvironmentName string = containerAppsManagedEnvironment.name
output containerAppsManagedEnvironmentResourceId string = containerAppsManagedEnvironment.id
output containerAppsManagedEnvironmentDefaultDomain string = containerAppsManagedEnvironment.properties.defaultDomain
