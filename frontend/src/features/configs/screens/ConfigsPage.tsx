import { useSearchParams } from "react-router-dom";
import { useConfigsListQuery } from "../api/queries";
import { selectConfigsRows } from "../model/selectors";
import { ConfigsTable } from "../components/ConfigsTable";
import { PageHeader } from "../../../components/PageHeader";
import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";

export default function ConfigsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTag = searchParams.get("tag");
  const searchValue = searchParams.get("search") || "";

  const { data, isLoading } = useConfigsListQuery();
  
  if (isLoading) {
    return (
      <div className="page-layout">
        <PageHeader title="Configs" />
        <LoadingSpinner />
      </div>
    );
  }

  const rows = selectConfigsRows(data);
  let filteredRows = activeTag 
    ? rows.filter(r => r.tags.includes(activeTag))
    : rows;
    
  if (searchValue) {
    const lowerSearch = searchValue.toLowerCase();
    filteredRows = filteredRows.filter(r => r.harness.toLowerCase().includes(lowerSearch));
  }

  const handleSearchChange = (val: string) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (val) {
        next.set("search", val);
      } else {
        next.delete("search");
      }
      return next;
    });
  };

  return (
    <div className="page-layout">
      <PageHeader 
        title="Configs" 
        subtitle="Manage configuration preferences across your harnesses."
      />
      <div className="page-content">
        <FilterBar 
          searchValue={searchValue} 
          onSearchChange={handleSearchChange}
          searchPlaceholder="Search configs..."
        />
        <ConfigsTable rows={filteredRows} />
      </div>
    </div>
  );
}
