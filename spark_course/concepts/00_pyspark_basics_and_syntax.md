# Concept 00: PySpark Basics & Syntax

**Covers:**
- Installing PySpark and starting a Spark session (your "cluster," even on a laptop)
- Reading and inspecting data
- `select`, `filter`/`where`, `withColumn`, rename patterns
- `groupBy` + aggregations, `orderBy`
- Joins (all the join types, and the classic ambiguous-column trap)
- Null handling, `union`, `distinct`
- The `pyspark.sql.functions` library (imported as `F` — you'll see this everywhere)
- Writing data back out, and running raw SQL against a DataFrame
- A pandas -> PySpark cheat-sheet, and the mistakes every beginner makes

> **Note:** this file isn't in the source YouTube playlist (that playlist assumes you
> already know this). It's added here because every other file in this course uses
> `select`/`filter`/`join`/`withColumn` freely, and you need this vocabulary before
> [Concept 01](01_spark_core_concepts.md) makes sense.

Everything below runs against a real local Spark session — `pip install pyspark`
(needs Java 8/11/17 on your machine) and paste any snippet into a `python3` shell.

---

## 1. Starting a Spark Session ("starting the cluster")

There's no separate "start the cluster" step when you're learning locally — creating
a `SparkSession` **is** starting Spark. In local mode, Spark just spins up worker
threads inside your own Python process instead of talking to real remote machines.

```python
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("MyFirstApp")       # name shown in the Spark UI (http://localhost:4040)
    .master("local[*]")          # "local[*]" = use all cores on this machine
    .getOrCreate()                # reuse an existing session in this process, or create one
)

spark.sparkContext.setLogLevel("WARN")   # Spark's default logging is very noisy
```

`master` options:

```text
local            -> 1 thread, no parallelism
local[4]         -> 4 threads
local[*]         -> all available cores on this machine    <- what you want for learning
spark://host:7077 -> a real Spark Standalone cluster
yarn             -> a Hadoop YARN cluster
k8s://https://... -> Kubernetes
```

When you're done:

```python
spark.stop()
```

Every example below assumes `spark` already exists from the block above.

---

## 2. Reading Data

```python
# CSV
df = spark.read.csv("path/to/file.csv", header=True, inferSchema=True)

# Parquet (no need for header/inferSchema -- schema is embedded in the file)
df = spark.read.parquet("path/to/folder/")

# JSON
df = spark.read.json("path/to/file.json")

# Explicit schema (recommended for production -- inferSchema reads the whole
# file once just to guess types, which is slow and can guess wrong)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

schema = StructType([
    StructField("customer_id", IntegerType(), nullable=False),
    StructField("name",        StringType(),  nullable=True),
    StructField("amount",      DoubleType(),  nullable=True),
])
df = spark.read.csv("path/to/file.csv", header=True, schema=schema)
```

Also directly from Python data, handy for quick tests (which is exactly what
every simulation in this course uses instead of real files):

```python
data = [(1, "alice", 100.0), (2, "bob", 250.5)]
df = spark.createDataFrame(data, schema=["customer_id", "name", "amount"])
```

## 3. Inspecting a DataFrame

```python
df.show()              # print up to 20 rows (df.show(5, truncate=False) for more control)
df.printSchema()        # column names + types, tree format
df.columns              # -> ['customer_id', 'name', 'amount']   (a plain Python list)
df.dtypes               # -> [('customer_id', 'int'), ('name', 'string'), ...]
df.count()               # number of rows -- this is an ACTION (see Concept 01), triggers a full scan
df.describe().show()    # count/mean/stddev/min/max per numeric column
```

```text
Output of df.printSchema():
root
 |-- customer_id: integer (nullable = false)
 |-- name: string (nullable = true)
 |-- amount: double (nullable = true)
```

---

## 4. `select` — picking columns

```python
from pyspark.sql import functions as F   # you will import this in almost every file

df.select("customer_id", "amount").show()

df.select(F.col("customer_id"), F.col("amount")).show()   # same thing, explicit col()

df.select(F.col("amount").alias("order_amount")).show()    # rename while selecting

df.selectExpr("customer_id", "amount * 1.1 AS amount_with_tax").show()  # raw SQL expressions
```

`col("x")` vs the bare string `"x"`: both work in `select`/`filter`, but you
**need** `F.col(...)` the moment you want to call a method on it (`.alias()`,
`.cast()`, comparisons combined with `&`/`|`), so most people just always use it.

---

## 5. `filter` / `where` — picking rows

`filter` and `where` are exact aliases — pick whichever reads better in context.

```python
df.filter(F.col("amount") > 100).show()
df.where(F.col("name") == "alice").show()

# Multiple conditions -- MUST use &, |, ~ (not `and`/`or`/`not`), and
# MUST wrap each condition in parentheses because of Python operator precedence
df.filter((F.col("amount") > 100) & (F.col("name") != "bob")).show()
df.filter((F.col("amount") > 500) | (F.col("name") == "alice")).show()
df.filter(~(F.col("name") == "bob")).show()

# String/SQL-expression form -- reads closer to SQL, some people prefer it
df.filter("amount > 100 AND name != 'bob'").show()
```

**Common beginner mistake:** writing `df.filter(col("amount") > 100 and col("name") != "bob")`
using Python's `and`. Python's `and`/`or`/`not` can't be overloaded the way
`&`/`|`/`~` can, so this either throws or silently does the wrong thing —
always use `&` / `|` / `~` with parentheses around each side.

---

## 6. Renaming Columns

Three ways, pick based on how many columns you're renaming:

```python
# One column
df2 = df.withColumnRenamed("amount", "order_amount")

# Rename while selecting (good when you're already selecting/transforming)
df2 = df.select(F.col("amount").alias("order_amount"))

# Rename ALL columns at once, positionally -- careful, order must match exactly
df2 = df.toDF("id", "customer_name", "order_amount")
```

---

## 7. `withColumn` — adding or replacing a column

```python
df2 = df.withColumn("amount_with_tax", F.col("amount") * 1.1)

# Conditional logic: F.when(...).otherwise(...) is Spark's if/elif/else
df2 = df.withColumn(
    "tier",
    F.when(F.col("amount") >= 1000, "gold")
     .when(F.col("amount") >= 100, "silver")
     .otherwise("bronze"),
)

# Reusing an existing column name REPLACES it (this is fine and common)
df2 = df.withColumn("amount", F.round(F.col("amount"), 2))

df2 = df.drop("amount_with_tax")   # remove a column
```

> Calling `.withColumn()` in a loop to add many columns is a known anti-pattern
> (each call adds a step to the query plan) — for many columns at once, use a
> single `.select("*", expr1, expr2, ...)` or `.withColumns({...})` (Spark 3.3+) instead.

---

## 8. `groupBy` + Aggregations

```python
df.groupBy("tier").count().show()

df.groupBy("tier").agg(
    F.sum("amount").alias("total_amount"),
    F.avg("amount").alias("avg_amount"),
    F.count("*").alias("num_orders"),
    F.max("amount").alias("largest_order"),
).show()

df.groupBy("tier").agg(F.sum("amount")).orderBy(F.desc("sum(amount)")).show()
```

```text
+------+------------+-----------+----------+-------------+
|tier  |total_amount|avg_amount |num_orders|largest_order|
+------+------------+-----------+----------+-------------+
|gold  |5400.0      |1350.0     |4         |2000.0       |
|silver|860.0       |215.0      |4         |400.0        |
|bronze|150.0       |50.0       |3         |80.0         |
+------+------------+-----------+----------+-------------+
```

This is different from a window function (running totals, rankings without
collapsing rows) — see [Concept 16: Window Functions](16_window_functions.md).

---

## 9. `orderBy` / `sort`

```python
df.orderBy("amount").show()                      # ascending by default
df.orderBy(F.col("amount").desc()).show()
df.orderBy(F.desc("amount")).show()               # shorthand, same thing
df.orderBy("tier", F.col("amount").desc()).show() # multiple sort keys, mixed direction
```

---

## 10. Joins

```python
orders = spark.createDataFrame(
    [(1, 101, 250.0), (2, 102, 90.0), (3, 999, 40.0)],
    ["order_id", "customer_id", "amount"],
)
customers = spark.createDataFrame(
    [(101, "alice"), (102, "bob")],
    ["customer_id", "name"],
)

orders.join(customers, on="customer_id", how="inner").show()
```

All join types (`how=`):

```text
"inner"           -> only matching rows on both sides (default if you omit `how`)
"left" / "left_outer"   -> all rows from the left, nulls where right has no match
"right" / "right_outer" -> all rows from the right, nulls where left has no match
"outer" / "full"        -> all rows from both sides, nulls where either side has no match
"left_semi"       -> rows from the left that HAVE a match on the right (like a filter,
                     right-side columns are NOT included -- common for existence checks)
"left_anti"       -> rows from the left that have NO match on the right (opposite of semi)
"cross"           -> every row x every row (cartesian) -- see Concept 14, almost never what you want
```

```python
orders.join(customers, on="customer_id", how="left").show()
orders.join(customers, on="customer_id", how="left_anti").show()   # orders with no matching customer (order_id 3)
```

**The #1 join gotcha — ambiguous column names.** If both sides have a column
with the same name and you join on a *different* condition (not a plain
`on="shared_col"` string), Spark keeps both copies and can't tell them apart
afterward:

```python
# BAD -- both DataFrames have `customer_id`, and joining on an *expression*
# (not a bare column-name string) keeps both copies in the result:
bad = orders.join(customers, orders.customer_id == customers.customer_id)
bad.select("customer_id")   # AnalysisException: Reference 'customer_id' is ambiguous

# FIX 1 (preferred): join on the column name as a plain string -- Spark
# automatically de-duplicates it into a single output column
good = orders.join(customers, on="customer_id", how="inner")

# FIX 2: alias the DataFrames first, then you can address each side explicitly
o, c = orders.alias("o"), customers.alias("c")
good2 = o.join(c, o.customer_id == c.customer_id).select("o.*", "c.name")
```

---

## 11. `union` and `distinct`

```python
more_orders = spark.createDataFrame([(4, 101, 60.0)], ["order_id", "customer_id", "amount"])

orders.union(more_orders).show()          # matches by POSITION -- columns must already be in the same order
orders.unionByName(more_orders).show()     # matches by NAME -- safer, use this by default

df.distinct().show()                      # drop full-row duplicates
df.dropDuplicates(["customer_id"]).show()  # drop duplicates by a subset of columns (keeps one arbitrary row per key)
```

---

## 12. Nulls

```python
df.filter(F.col("amount").isNull()).show()
df.filter(F.col("amount").isNotNull()).show()

df.na.drop()                          # drop rows with ANY null
df.na.drop(subset=["amount"])         # drop rows null in THIS column only
df.na.fill(0, subset=["amount"])      # replace nulls with a value
df.fillna({"amount": 0, "name": "unknown"})   # different fill value per column
```

---

## 13. `pyspark.sql.functions` — the library you'll import everywhere

By convention, almost every PySpark file starts with:

```python
from pyspark.sql import functions as F
```

A few of the most-used functions (there are 300+; these cover 90% of daily use):

```text
F.col("x")                       column reference
F.lit(5)                         a literal value as a column (e.g. df.withColumn("k", F.lit(1)))
F.when(cond, val).otherwise(v)    if/elif/else
F.concat(F.col("a"), F.col("b")) string concatenation
F.round(F.col("x"), 2)            round a number
F.cast("double") / .cast(DoubleType())   change a column's type
F.to_date(F.col("s"), "yyyy-MM-dd")      parse a string into a date
F.date_add(F.col("d"), 7)         date arithmetic
F.current_date() / F.current_timestamp()
F.upper(...) / F.lower(...) / F.trim(...) / F.length(...)
F.coalesce(F.col("a"), F.col("b"))       first non-null value across columns
F.array(...), F.explode(...)     build/flatten array columns (used a lot in Concept 08: Salting)
F.broadcast(df)                   hint: broadcast this DataFrame in a join (Concept 09)
```

---

## 14. Writing Data Out

```python
df.write.mode("overwrite").parquet("output/path/")     # "overwrite" | "append" | "error" | "ignore"
df.write.mode("overwrite").partitionBy("tier").parquet("output/path/")  # one subfolder per tier value
df.write.mode("overwrite").option("header", True).csv("output/path/")
```

---

## 15. SQL — the same thing, written as SQL

Every DataFrame can become a queryable "table" for the duration of the session:

```python
df.createOrReplaceTempView("orders")

spark.sql("""
    SELECT tier, SUM(amount) AS total_amount
    FROM orders
    GROUP BY tier
    ORDER BY total_amount DESC
""").show()
```

`spark.sql(...)` returns a normal DataFrame — you can keep chaining `.filter()`,
`.join()`, etc. on the result. DataFrame API and SQL compile to the **exact
same** physical plan (see [Concept 02](02_query_plans_and_explain.md)) — pick
whichever is more readable for a given query, there's no performance difference.

---

## 16. If You Already Know pandas

```text
pandas                          PySpark
----------------------------     ----------------------------------------
df.head()                        df.show(5)
df.shape                         (df.count(), len(df.columns))
df['col']                        df.select('col')  /  F.col('col')
df[df.amount > 100]              df.filter(F.col('amount') > 100)
df.rename(columns={...})          df.withColumnRenamed(...) / .toDF(...)
df.groupby('x').sum()            df.groupBy('x').sum()  /  .agg(F.sum(...))
df.sort_values('x')              df.orderBy('x')
df.merge(other, on='k')          df.join(other, on='k')
df.drop_duplicates()              df.dropDuplicates()
df.fillna(0)                      df.fillna(0)
df.isnull()                       F.col('x').isNull()
```

The one habit to unlearn: pandas runs every line immediately. PySpark **doesn't**
— see [Concept 01](01_spark_core_concepts.md) for lazy evaluation, which is the
single biggest mental-model shift coming from pandas.

---

## Key Takeaways

- Creating a `SparkSession` *is* "starting the cluster" — in local mode it's just threads in your own process; `master("local[*]")` is what you want while learning.
- `select`/`filter`/`withColumn` are transformations (lazy); `show()`/`count()`/`collect()` are actions that actually run something — this becomes important the moment you start caring about performance (Concept 01 onward).
- Always combine filter conditions with `&` / `|` / `~` and parentheses, never Python's `and`/`or`/`not`.
- The classic join bug is an ambiguous column name — join on a plain string column name (`on="col"`) instead of an equality expression whenever both sides share that column name.
- `unionByName` is almost always safer than `union` (which matches by column position).
- `pyspark.sql.functions as F` is where basically every column-level operation lives — get comfortable skimming its docs.
- DataFrame API and `spark.sql(...)` produce the identical physical plan — there is no "SQL is slower" penalty.
- Once this vocabulary feels natural, Concept 01 onward is about what Spark does *underneath* these calls — that's where the actual tuning skill lives.
