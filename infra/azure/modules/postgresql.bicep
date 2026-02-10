targetScope = 'resourceGroup'

@description('Azure location for PostgreSQL resources.')
param location string

@description('PostgreSQL Flexible Server name.')
param postgresqlServerName string

@description('PostgreSQL administrator login name.')
param postgresqlAdministratorLogin string = ''

@secure()
@description('PostgreSQL administrator login password.')
param postgresqlAdministratorPassword string = ''

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

@allowed([
  'postgresql_only'
  'microsoft_entra_only'
  'postgresql_and_microsoft_entra'
])
@description('PostgreSQL authentication mode.')
param postgresqlAuthenticationMode string

@description('Allow public access from Azure services using PostgreSQL firewall 0.0.0.0 rule.')
param postgresqlAllowPublicAccessFromAzureServices bool

@description('Public IPv4 allowlist applied to PostgreSQL firewall rules.')
param publicIpv4Allowlist array

@minLength(1)
@description('Access control group name prefix used to derive Entra group principal names.')
param accessControlGroupNamePrefix string

@description('Microsoft Entra object ID for the database admin group. Leave empty to skip assigning a dedicated Entra admin group.')
param databaseAdminsEntraGroupObjectId string = ''

var postgresqlUsesMicrosoftEntraAuthentication = contains([
  'microsoft_entra_only'
  'postgresql_and_microsoft_entra'
], postgresqlAuthenticationMode)

var postgresqlUsesPasswordAuthentication = contains([
  'postgresql_only'
  'postgresql_and_microsoft_entra'
], postgresqlAuthenticationMode)

var effectivePostgresqlAdministratorLogin = empty(postgresqlAdministratorLogin) ? 'adeadmin' : postgresqlAdministratorLogin

var normalizedAccessControlGroupNamePrefix = toLower(accessControlGroupNamePrefix)
var databaseAdminsEntraGroupPrincipalName = '${normalizedAccessControlGroupNamePrefix}-db-admins'
var hasDatabaseAdminsEntraGroupObjectId = !empty(databaseAdminsEntraGroupObjectId)

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
  properties: union(
    {
      version: any(postgresqlVersion)
      storage: {
        storageSizeGB: postgresqlStorageSizeGb
      }
      network: {
        publicNetworkAccess: 'Enabled'
      }
      authConfig: {
        activeDirectoryAuth: postgresqlUsesMicrosoftEntraAuthentication ? 'Enabled' : 'Disabled'
        passwordAuth: postgresqlUsesPasswordAuthentication ? 'Enabled' : 'Disabled'
        tenantId: tenant().tenantId
      }
    },
    postgresqlUsesPasswordAuthentication
      ? {
          administratorLogin: effectivePostgresqlAdministratorLogin
          administratorLoginPassword: postgresqlAdministratorPassword
        }
      : {}
  )
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

resource postgresqlEntraAdministrator 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = if (postgresqlUsesMicrosoftEntraAuthentication && hasDatabaseAdminsEntraGroupObjectId) {
  parent: postgresqlServer
  name: databaseAdminsEntraGroupObjectId
  properties: {
    principalName: databaseAdminsEntraGroupPrincipalName
    principalType: 'Group'
    tenantId: tenant().tenantId
  }
}

output postgresqlServerName string = postgresqlServer.name
output postgresqlServerResourceId string = postgresqlServer.id
output postgresqlFullyQualifiedDomainName string = postgresqlServer.properties.fullyQualifiedDomainName
output postgresqlUsesMicrosoftEntraAuthentication bool = postgresqlUsesMicrosoftEntraAuthentication
output postgresqlLocalAuthenticationEnabled bool = postgresqlUsesPasswordAuthentication
output postgresqlProductionDatabaseName string = productionPostgresqlDatabase.name
output postgresqlDevelopmentDatabaseName string = deployDevelopmentEnvironment ? developmentPostgresqlDatabase!.name : ''
