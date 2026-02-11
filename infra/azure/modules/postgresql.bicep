targetScope = 'resourceGroup'

@description('Azure location for PostgreSQL resources.')
param location string

@description('PostgreSQL Flexible Server name.')
param postgresqlServerName string

@description('PostgreSQL major version (for example, 16).')
param postgresqlVersion string

@description('PostgreSQL compute tier (for example, Burstable).')
param postgresqlSkuTier string

@description('PostgreSQL SKU name (for example, Standard_B1ms).')
param postgresqlSkuName string

@minValue(32)
@description('PostgreSQL storage size in GiB.')
param postgresqlStorageSizeGb int

@description('Deploy development database resources when true.')
param deployDevelopmentEnvironment bool

@description('Production PostgreSQL database name.')
param postgresqlProductionDatabaseName string

@description('Development PostgreSQL database name.')
param postgresqlDevelopmentDatabaseName string

@description('Allow public access from Azure services using PostgreSQL firewall 0.0.0.0 rule.')
param postgresqlAllowPublicAccessFromAzureServices bool

@description('Public IPv4 allowlist applied to PostgreSQL firewall rules.')
param publicIpv4Allowlist array

var postgresqlAllowlistFirewallRules = [for ipAddress in publicIpv4Allowlist: {
  name: 'allow-ip-${replace(ipAddress, '.', '-')}'
  startIpAddress: ipAddress
  endIpAddress: ipAddress
}]

var postgresqlFirewallRules = concat(
  postgresqlAllowPublicAccessFromAzureServices
    ? [
        {
          name: 'allow-azure-services'
          startIpAddress: '0.0.0.0'
          endIpAddress: '0.0.0.0'
        }
      ]
    : [],
  postgresqlAllowlistFirewallRules
)

resource postgresqlServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresqlServerName
  location: location
  sku: {
    name: postgresqlSkuName
    tier: postgresqlSkuTier
  }
  properties: {
    version: any(postgresqlVersion)
    storage: {
      storageSizeGB: postgresqlStorageSizeGb
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: tenant().tenantId
    }
  }
}

resource productionPostgresqlDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresqlServer
  name: postgresqlProductionDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource developmentPostgresqlDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = if (deployDevelopmentEnvironment) {
  parent: postgresqlServer
  name: postgresqlDevelopmentDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresqlFirewallRuleResources 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = [for firewallRule in postgresqlFirewallRules: {
  parent: postgresqlServer
  name: firewallRule.name
  properties: {
    startIpAddress: firewallRule.startIpAddress
    endIpAddress: firewallRule.endIpAddress
  }
}]

output postgresqlServerName string = postgresqlServer.name
output postgresqlServerResourceId string = postgresqlServer.id
output postgresqlFullyQualifiedDomainName string = postgresqlServer.properties.fullyQualifiedDomainName
output postgresqlProductionDatabaseName string = productionPostgresqlDatabase.name
output postgresqlDevelopmentDatabaseName string = deployDevelopmentEnvironment ? developmentPostgresqlDatabase!.name : ''
