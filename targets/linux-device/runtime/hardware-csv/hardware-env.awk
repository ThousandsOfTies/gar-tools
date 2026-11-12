# Read single-record CSV (quoted commas and doubled quotes supported).
function fail(message) { print "hardware-run: " message > "/dev/stderr"; failed=1; exit 2 }
function parse(text, cells,    i,n,c,quoted,closed,value) {
    for (i in cells) delete cells[i]
    sub(/\r$/, "", text)
    n=1; value=""; quoted=0; closed=0
    for (i=1; i<=length(text); i++) {
        c=substr(text,i,1)
        if (quoted) {
            if (c=="\"") {
                if (substr(text,i+1,1)=="\"") { value=value "\""; i++ }
                else { quoted=0; closed=1 }
            } else value=value c
        } else if (c==",") { cells[n++]=value; value=""; closed=0 }
        else if (c=="\"" && value=="" && !closed) quoted=1
        else if (closed || c=="\"") fail("malformed CSV: " FILENAME ":" FNR)
        else value=value c
    }
    if (quoted) fail("multiline or unterminated CSV record: " FILENAME ":" FNR)
    cells[n]=value
    return n
}
function quote(value,    i,c,result) {
    result="'"
    for (i=1;i<=length(value);i++) {
        c=substr(value,i,1)
        result=result (c=="'" ? "'\"'\"'" : c)
    }
    return result "'"
}
{
    if (FNR==1) sub(/^\357\273\277/, "", $0)
    count=parse($0, cells)
    table=FILENAME; sub(/^.*\//,"",table); sub(/\.csv$/,"",table)
    if (FNR==1) {
        for (i in columns) delete columns[i]
        for (i=1;i<=count;i++) {
            if (cells[i]=="" || cells[i] in columns) fail("invalid CSV header")
            columns[cells[i]]=i
        }
        width=count
        if (table=="environment") {
            if (count!=4 || cells[1]!="variable" || cells[2]!="table" || cells[3]!="name" || cells[4]!="field")
                fail("environment.csv requires variable,table,name,field")
        } else if (!("name" in columns)) fail("table requires name column")
        next
    }
    if (count!=width) fail("CSV column count mismatch: " FILENAME ":" FNR)
    if (table=="environment") {
        variable=cells[1]
        if (variable !~ /^[A-Z][A-Z0-9_]*$/ || variable in variables) fail("invalid or duplicate variable")
        if (cells[2]!="gpio" && cells[2]!="spi") fail("unsupported runtime table")
        variables[variable]=cells[2] SUBSEP cells[3] SUBSEP cells[4]
        mapping_count++
    } else {
        name=cells[columns["name"]]
        if (name=="" || (table SUBSEP name) in rows) fail("missing or duplicate hardware name")
        rows[table SUBSEP name]=1
        for (field in columns) values[table SUBSEP name SUBSEP field]=cells[columns[field]]
    }
}
END {
    if (failed) exit 2
    if (!mapping_count) fail("environment.csv must contain runtime references")
    for (variable in variables) {
        key=variables[variable]
        if (!(key in values) || values[key]=="") fail("missing CSV reference for " variable)
    }
    for (variable in variables)
        if (ENVIRON[variable]=="") print "export " variable "=" quote(values[variables[variable]])
}
