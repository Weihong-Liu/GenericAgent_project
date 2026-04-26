import { Box, Text } from "ink";
import React from "react";

export interface SearchBoxProps {
  query: string;
  prompt?: string;
  accentColor?: string;
  placeholder?: string;
}

export function SearchBox({
  query,
  prompt = "›",
  accentColor = "cyan",
  placeholder = "",
}: SearchBoxProps): React.ReactElement {
  return (
    <Box>
      <Text color={accentColor}>{prompt} </Text>
      {query ? (
        <Text>{query}</Text>
      ) : placeholder ? (
        <Text color="gray" dimColor>
          {placeholder}
        </Text>
      ) : null}
      <Text color="gray">▍</Text>
    </Box>
  );
}
