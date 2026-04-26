import { Box, Text } from "ink";
import React from "react";

export interface TabItem {
  id: string;
  label: string;
}

interface TabsProps {
  tabs: readonly TabItem[];
  activeId: string;
  accentColor?: string;
}

export function Tabs({ tabs, activeId, accentColor = "cyan" }: TabsProps): React.ReactElement {
  return (
    <Box>
      {tabs.map((tab, index) => {
        const active = tab.id === activeId;
        return (
          <Text key={tab.id} color={active ? accentColor : "gray"} bold={active}>
            {index > 0 ? "  " : ""}
            {active ? "● " : "○ "}
            {tab.label}
          </Text>
        );
      })}
    </Box>
  );
}
