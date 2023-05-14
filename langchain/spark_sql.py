from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, List, Optional

from pyspark.errors import PySparkException

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, Row, SparkSession

from langchain import SQLDatabase


class SparkSQL(SQLDatabase):
    def __init__(
        self,
        spark_session: Optional[SparkSession] = None,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        ignore_tables: Optional[List[str]] = None,
        include_tables: Optional[List[str]] = None,
        sample_rows_in_table_info: int = 3,
    ):
        try:
            from pyspark.sql import SparkSession
        except ImportError:
            raise ValueError(
                "pyspark is not installed. Please install it with `pip install pyspark`"
            )

        self._spark = (
            spark_session if spark_session else SparkSession.builder.getOrCreate()
        )
        if catalog is not None:
            self._spark.catalog.setCurrentCatalog(catalog)
        if schema is not None:
            self._spark.catalog.setCurrentDatabase(schema)

        self._all_tables = set(self._get_all_table_names())
        super()._init_table_options(
            ignore_tables=ignore_tables,
            include_tables=include_tables,
            sample_rows_in_table_info=sample_rows_in_table_info,
        )

    @classmethod
    def from_uri(
        cls, database_uri: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> SQLDatabase:
        """Creating a remote Spark Session via Spark connect.
        For example: SparkSQL.from_uri("sc://localhost:15002")
        """
        try:
            from pyspark.sql import SparkSession
        except ImportError:
            raise ValueError(
                "pyspark is not installed. Please install it with `pip install pyspark`"
            )

        spark = SparkSession.builder.remote(database_uri).getOrCreate()
        return cls(spark, **kwargs)

    @property
    def dialect(self) -> str:
        return "spark"

    def get_usable_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        if self._include_tables:
            return self._include_tables
        # sorting the result can help LLM understanding it.
        return sorted(self._all_tables - self._ignore_tables)

    def _get_all_table_names(self) -> Iterable[str]:
        rows = self._spark.sql("SHOW TABLES").select("tableName").collect()
        return list(map(lambda row: row.tableName, rows))

    def _get_create_table_stmt(self, table: str) -> str:
        statement = (
            self._spark.sql(f"SHOW CREATE TABLE {table}").collect()[0].createtab_stmt
        )
        # Ignore the data source provider and options to reduce the number of tokens.
        using_clause_index = statement.find("USING")
        return statement[:using_clause_index] + ";"

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        all_table_names = self.get_usable_table_names()
        if table_names is not None:
            missing_tables = set(table_names).difference(all_table_names)
            if missing_tables:
                raise ValueError(f"table_names {missing_tables} not found in database")
            all_table_names = table_names
        tables = []
        for table_name in all_table_names:
            table_info = self._get_create_table_stmt(table_name)
            if self._sample_rows_in_table_info:
                table_info += "\n\n/*"
                table_info += f"\n{self._get_sample_spark_rows(table_name)}\n"
                table_info += "*/"
            tables.append(table_info)
        final_str = "\n\n".join(tables)
        return final_str

    def _get_sample_spark_rows(self, table: str) -> str:
        query = f"SELECT * FROM {table} LIMIT {self._sample_rows_in_table_info}"
        df = self._spark.sql(query)
        columns_str = "\t".join(list(map(lambda f: f.name, df.schema.fields)))
        try:
            sample_rows = self._get_dataframe_results(df)
            # save the sample rows in string format
            sample_rows_str = "\n".join(["\t".join(row) for row in sample_rows])
        except Exception:
            sample_rows_str = ""

        return (
            f"{self._sample_rows_in_table_info} rows from {table} table:\n"
            f"{columns_str}\n"
            f"{sample_rows_str}"
        )

    def _convert_row_as_tuple(self, row: Row) -> tuple:
        return tuple(map(str, row.asDict().values()))

    def _get_dataframe_results(self, df: DataFrame) -> list:
        return list(map(self._convert_row_as_tuple, df.collect()))

    def run(self, command: str, fetch: str = "all") -> str:
        df = self._spark.sql(command)
        if fetch == "one":
            df = df.limit(1)
        return str(self._get_dataframe_results(df))

    def run_no_throw(self, command: str, fetch: str = "all") -> str:
        """Execute a SQL command and return a string representing the results.

        If the statement returns rows, a string of the results is returned.
        If the statement returns no rows, an empty string is returned.

        If the statement throws an error, the error message is returned.
        """
        try:
            return self.run(command, fetch)
        except PySparkException as e:
            """Format the error message"""
            return f"Error: {e}"
