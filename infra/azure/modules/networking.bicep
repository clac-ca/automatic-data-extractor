targetScope = 'resourceGroup'

@description('Azure location for networking resources.')
param location string

@description('Virtual Network name.')
param virtualNetworkName string

@description('Virtual Network address prefix (CIDR).')
param virtualNetworkAddressPrefix string

@description('Container Apps delegated subnet name.')
param containerAppsSubnetName string

@description('Container Apps delegated subnet address prefix (CIDR).')
param containerAppsSubnetAddressPrefix string

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: virtualNetworkName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        virtualNetworkAddressPrefix
      ]
    }
    subnets: [
      {
        name: containerAppsSubnetName
        properties: {
          addressPrefix: containerAppsSubnetAddressPrefix
          delegations: [
            {
              name: 'container-apps-environment-delegation'
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

resource containerAppsSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' existing = {
  parent: virtualNetwork
  name: containerAppsSubnetName
}

output virtualNetworkName string = virtualNetwork.name
output virtualNetworkResourceId string = virtualNetwork.id
output containerAppsSubnetName string = containerAppsSubnet.name
output containerAppsSubnetResourceId string = containerAppsSubnet.id
