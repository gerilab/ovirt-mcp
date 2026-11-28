==============================================================================
oVirt / OLVM MCP Server - SDK Parity & Coverage Audit Report
==============================================================================
Total Registered MCP Tools:  186
Audited Resource Domains:    11
Total SDK Properties:        434
Exposed in MCP Models:       164 (37.8% overall property coverage)
------------------------------------------------------------------------------
Resource Domain            SDK Type         SDK Props   MCP Fields  Coverage %
------------------------------------------------------------------------------
Host                       Host             58          23             39.7%
Virtual Machine (Vm)       Vm               90          35             38.9%
Virtual Disk               Disk             43          18             41.9%
Storage Domain             StorageDomain    34          19             55.9%
Cluster                    Cluster          49          27             55.1%
Logical Network            Network          24          10             41.7%
Template                   Template         62          5               8.1%
Data Center                DataCenter       18          8              44.4%
Resource Quota             Quota            15          3              20.0%
VM Pool                    VmPool           20          8              40.0%
User Account               User             21          8              38.1%
------------------------------------------------------------------------------
Service Action / Mutation Tool Coverage:
------------------------------------------------------------------------------
SDK Service                Total Methods   Covered Tools   Coverage %
------------------------------------------------------------------------------
VmService                  26              19                 73.1%
HostService                20              16                 80.0%
StorageDomainService       6               5                  83.3%
ClusterService             6               4                  66.7%
DiskService                9               6                  66.7%
TemplateService            5               3                  60.0%
DataCenterService          4               2                  50.0%
NetworkService             2               2                 100.0%
VmPoolService              3               3                 100.0%
==============================================================================
Remaining Unmapped Service Actions (Candidates for Future Parity Expansion):
  * VmService: detach, export_to_export_domain, export_to_path_on_host, logon, maintenance
  * HostService: approve, copy_host_networks, discover_iscsi, unregistered_storage_domains_discover
  * StorageDomainService: is_attached
  * ClusterService: refresh_gluster_heal_status, upgrade
  * DiskService: convert, refresh_lun, update
  * TemplateService: export_to_export_domain, export_to_path_on_host
  * DataCenterService: set_master, update
==============================================================================
