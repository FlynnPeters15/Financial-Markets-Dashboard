import { ResponsiveTreeMap } from '@nivo/treemap';
import { CompanyQuote } from '../lib/api';
import { getColorForPercentChange, formatPercent } from '../lib/format';

interface HeatmapTreemapProps {
  data: CompanyQuote[];
  onNodeClick: (company: CompanyQuote) => void;
}

interface TreemapNode {
  id: string;
  value: number;
  color: string;
  company: CompanyQuote;
}

export function HeatmapTreemap({ data, onNodeClick }: HeatmapTreemapProps) {
  if (data.length === 0) {
    return (
      <div className="w-full h-[600px] flex items-center justify-center text-muted-foreground">
        No data available
      </div>
    );
  }

  const nodes = data.map((company) => ({
    id: company.symbol,
    value: 1, // Equal weights for now (can use marketCap if available)
    color: getColorForPercentChange(company.pctChange, company.status),
    company,
  }));

  const root: TreemapNode & { children: (TreemapNode & { company: CompanyQuote })[] } = {
    id: 'root',
    value: 0,
    color: '#6b7280',
    company: {} as CompanyQuote,
    children: nodes,
  };

  return (
    <div className="w-full h-[600px]">
      <ResponsiveTreeMap
        data={root}
        value="value"
        identity="id"
        valueFormat=".2s"
        margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
        label={(node) => {
          const nodeData = node.data as TreemapNode & { company?: CompanyQuote };
          const company = nodeData.company;
          if (!company || !company.symbol) return node.id;
          const pct = formatPercent(company.pctChange);
          return `${node.id}\n${pct}`;
        }}
        labelSkipSize={12}
        labelTextColor="#ffffff"
        parentLabelPosition="left"
        parentLabelTextColor="#ffffff"
        colors={(node) => {
          const treemapNode = node.data as TreemapNode & { color?: string };
          return treemapNode.color || '#6b7280';
        }}
        borderColor={{
          from: 'color',
          modifiers: [['darker', 0.1]],
        }}
        borderWidth={2}
        animate={true}
        motionConfig="gentle"
        tooltip={({ node }) => {
          const treemapNode = node.data as TreemapNode & { company?: CompanyQuote };
          const company = treemapNode.company;
          if (!company || !company.symbol) return null;

          return (
            <div className="bg-card border border-border rounded-lg p-3 shadow-lg max-w-xs">
              <div className="font-semibold mb-1">{company.name}</div>
              <div className="text-sm text-muted-foreground mb-2">{company.symbol}</div>
              <div className="text-sm space-y-1">
                <div>Sector: {company.subIndustry}</div>
                <div>Close: {company.close !== null ? `$${company.close.toFixed(2)}` : 'N/A'}</div>
                <div>
                  Change: {formatPercent(company.pctChange)} (
                  {company.change !== null ? `$${company.change.toFixed(2)}` : 'N/A'})
                </div>
                {company.source && (
                  <div className="text-xs text-muted-foreground mt-2">
                    Source: {company.source.replace('_', ' ')}
                  </div>
                )}
              </div>
            </div>
          );
        }}
        onClick={(node) => {
          const treemapNode = node.data as TreemapNode & { company?: CompanyQuote };
          if (treemapNode.company && treemapNode.company.symbol) {
            onNodeClick(treemapNode.company);
          }
        }}
        theme={{
          background: 'transparent',
          text: {
            fontSize: 12,
            fill: '#ffffff',
            outlineWidth: 0,
            outlineColor: 'transparent',
          },
          tooltip: {
            container: {
              background: 'transparent',
              fontSize: 12,
            },
          },
        }}
      />
    </div>
  );
}
